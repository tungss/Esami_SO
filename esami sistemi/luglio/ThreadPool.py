"""
Il codice del ThreadPool per l'appello di SO di Luglio 2026

Un ThreadPool gestisce un gruppo di Thread (Worker) ai quali vengono assegnati
dei compiti da eseguire, detti Job. Un Job e' un oggetto con un metodo execute()
(NOTA CHE un Job non e' un Thread, e' solo il "compito" che un Worker esegue),
"eseguire un job J" significa invocare J.execute().

Lo scopo tipico di un ThreadPool e' quello di limitare il numero di thread attivi in un dato momento, 
evitando di crearne uno per ogni job da eseguire. In questo modo c'è un maggior controllo sulle risorse del 
sistema e si riduce il sovraccarico di gestione dei thread.

Un Job viene sottomesso al ThreadPool con submit(): il pool deve eseguirlo il
prima possibile e rispettando l'ordine di sottomissione, in base alla
disponibilita' di thread liberi. Tutti i metodi pubblici devono essere
thread-safe.

Metodi messi a disposizione:

    ThreadPool(n_thread)  -> crea un pool con n_thread thread gia' avviati
    submit(job)            -> accoda un job ed esce subito (non bloccante)
    wait_for_start(job)    -> blocca il chiamante finche' un job non e' partito
    wait_for_finish(job)   -> blocca il chiamante finche' job non e' concluso
    pause()                -> sospende l'avvio di nuovi job (quelli in corso continuano)
    resume()                -> fa ripartire l'esecuzione dei job
    wait_for_all_running()  -> blocca il chiamante finche' tutti i job in corso non terminano
                                (non fa nulla sui job ancora in coda)
    wait_for_termination()  -> blocca il chiamante finche' non sono terminati sia i job
                                in corso sia quelli ancora in coda
    hurry_and_stop()        -> disabilita submit, fa terminare il prima possibile
                                tutti i job gia' in coda (creando, se serve, nuovi
                                thread fino a uno per ogni job in attesa),
                                poi esce quando tutto e' terminato

Se submit() viene chiamato dopo hurry_and_stop() viene sollevata un'eccezione
(SubmitDisabledException).
"""

from threading import RLock, Thread, Condition


class Job:
    """
    Classe base per i job eseguibili dal ThreadPool. Le sottoclassi devono
    ridefinire execute() con il lavoro effettivo da svolgere.

    Ogni Job porta con se' due Condition (start_cond, end_cond) create sullo
    STESSO lock del ThreadPool che lo eseguira': in questo modo il worker puo'
    modificare lo stato del job (running, terminato) e segnalare le due
    condition all'interno della sezione critica del pool, senza bisogno di un
    lock separato per ogni singolo job.
    """

    def __init__(self, lock):
        # Condition segnalata quando il job passa da "in coda" a "in esecuzione"
        self.start_cond = Condition(lock)
        # Condition segnalata quando il job termina l'esecuzione
        self.end_cond = Condition(lock)
        # True dal momento in cui un worker inizia ad eseguire execute()
        self.running = False
        # True dal momento in cui execute() e' terminato
        self.ended = False

    def execute(self):
        # Metodo da ridefinire nelle sottoclassi: e' il lavoro vero e proprio del job.
        raise NotImplementedError


class SubmitDisabledException(Exception):
    # Sollevata da submit() se il pool e' stato messo in stato "stopped" da hurry_and_stop().
    pass


class Worker(Thread):
    """
    Thread facente parte del thread pool, che pesca ripetutamente un job dalla coda del pool e lo esegue.
    Ogni worker vive per sempre in un ciclo a 5 fasi, descritte nel metodo run().
    """

    def __init__(self, pool):
        super().__init__()
        self.pool = pool

    def run(self):
        while True:
            #
            # Fase 1. Se il pool e' in pausa, il worker si mette in attesa qui
            # e non preleva nuovi job finche' non arriva una resume().
            # I job GIA' in esecuzione non vengono toccati da pause(): la pausa
            # agisce solo sui worker che stanno per prelevare un nuovo job.
            #
            self.pool.lock.acquire()
            while self.pool.paused:
                self.pool.restart_cond.wait()

            #
            # Fase 2. Prelievo del prossimo job dalla coda (ordine FIFO). Il worker si
            # blocca su job_disponibile se la coda e' vuota.
            #
            # Nota: e' possibile durante l'attesa di un nuovo job
            # arrivi una pause(). In tal caso questo worker prelevera' ed eseguira'
            # comunque un ultimo job prima di fermarsi al giro successivo. Non e'
            # un errore: la specifica garantisce solo che pause() blocchi
            # l'AVVIO di ulteriori job, non impone un istante preciso.
            #
            while len(self.pool.coda_job) == 0:
                    self.pool.job_disponibile.wait()
            job = self.pool.coda_job.pop(0)

            #
            # Fase 3. Segna il job come "in esecuzione" e sveglia chi era in
            # attesa su wait_for_start().
            #
            job.running = True
            self.pool.running += 1
            job.start_cond.notify_all()

            #
            # Fase 4. Esecuzione vera e propria del job. Va fatta SENZA possedere
            # il lock del pool, altrimenti i job non potrebbero mai essere
            # eseguiti in parallelo tra loro (e un job "lento" bloccherebbe tutte
            # le operazioni del pool, incluse submit/pause/ecc.).
            #
            self.pool.lock.release()
            job.execute()

            #
            # Fase 5. Segna il job come "terminato", decrementa il conteggio dei
            # job in esecuzione e sveglia chi era in attesa su wait_for_finish()
            # e/o su wait_for_all_running()/wait_for_termination() (queste ultime
            # solo quando l'ultimo job in corso termina, cioe' quando running
            # torna a 0).
            #
            with self.pool.lock:
                job.ended = True
                self.pool.running -= 1
                if self.pool.running == 0:
                    self.pool.all_terminated.notify_all()
                job.end_cond.notify_all()


class ThreadPool:
    def __init__(self, n_thread):
        """
        Crea un ThreadPool con n_thread worker gia' avviati e pronti ad
        eseguire eventuali Job che verranno sottomessi con submit().
        """

        # Unico lock che protegge TUTTO lo stato condiviso del pool (coda dei
        # job, contatori, flag paused/stopped) e, per costruzione, anche lo
        # stato dei singoli Job (running/ended), dato che le loro Condition
        # sono create su questo stesso lock.
        self.lock = RLock()

        # Condition per svegliare chi e' in attesa su wait_for_all_running() o su
        # wait_for_termination(): notificata quando l'ultimo job in esecuzione
        # termina (running torna a 0).
        self.all_terminated = Condition(self.lock)
        # Condition su cui aspettano i worker quando il pool e' in pausa:
        # notificata da resume().
        self.restart_cond = Condition(self.lock)
        # Condition su cui aspettano i worker quando la coda job e' vuota:
        # notificata da submit() ogni volta che arriva un nuovo job.
        self.job_disponibile = Condition(self.lock)

        # True se il pool e' in pausa: i worker non prelevano nuovi job, ma
        # submit() resta volutamente comunque utilizzabile).
        self.paused = False
        # True dopo una chiamata a hurry_and_stop(): da questo momento submit()
        # deve sollevare SubmitDisabledException.
        self.stopped = False
        # Numero di job attualmente in esecuzione (Fase 3 completata, Fase 5 no).
        self.running = 0
        # Coda FIFO dei job sottomessi e non ancora prelevati da un worker.
        self.coda_job = []

        # Elenco dei worker attivi (puo' crescere quando invochi hurry_and_stop()).
        self.workers = []
        for _ in range(n_thread):
            worker = Worker(self)
            self.workers.append(worker)
            worker.start()

    def submit(self, job):
        """
        Accoda un Job per l'esecuzione ed esce subito (non aspetta che parta
        ne' che finisca). Solleva SubmitDisabledException se il pool e' stato
        fermato con hurry_and_stop().
        """
        with self.lock:
            if self.stopped:
                raise SubmitDisabledException()
            self.coda_job.append(job)
            # Sveglia un eventuale worker in attesa di un job da eseguire.
            self.job_disponibile.notify_all()

    def wait_for_start(self, job):
        """
        Blocca il chiamante finche' l'esecuzione di job non risulta
        effettivamente iniziata. Controlla anche "terminato" per non restare
        bloccati per sempre nel caso in cui il job sia gia' partito E finito
        prima ancora che questo metodo venisse chiamato (job molto veloce).
        """
        with self.lock:
            while not job.running and not job.ended:
                job.start_cond.wait()

    def wait_for_finish(self, job):
        """
        Blocca il chiamante finche' job non risulta eseguito e concluso.
        """
        with self.lock:
            while not job.ended:
                job.end_cond.wait()

    def pause(self):
        """
        Sospende l'avvio di ulteriori job: i worker che stanno gia' eseguendo
        un job lo portano a termine normalmente, ma nessun worker ne prelevera'
        di nuovi finche' non arriva una resume(). E' comunque possibile
        continuare a chiamare submit() durante la pausa.
        """
        with self.lock:
            self.paused = True

    def resume(self):
        """
        Riprende l'esecuzione normale dei job, svegliando tutti i worker
        eventualmente bloccati in attesa a causa di pause().
        """
        with self.lock:
            self.paused = False
            self.restart_cond.notify_all()

    def wait_for_all_running(self):
        """
        Blocca il chiamante finche' tutti i job *attualmente* in esecuzione non
        terminano (running torna a 0). Non dice nulla sui job non ancora
        prelevati dalla coda. Se il pool non e' in pausa, running potrebbe non scendere mai a 0.
        Per aspettare specificamente che tutto termini, anche i job in coda,
        va usato wait_for_termination() (o hurry_and_stop() per farli anche
        terminare il prima possibile).
        """
        with self.lock:
            while self.running > 0:
                self.all_terminated.wait()

    def wait_for_termination(self):
        """
        Blocca il chiamante finche' non sono terminati sia i job attualmente in
        esecuzione (running torna a 0) sia quelli ancora in coda (coda_job
        diventa vuota). A differenza di wait_for_all_running(), tiene conto
        anche dei job non ancora prelevati da un worker.
        """
        with self.lock:
            while self.running > 0 or len(self.coda_job) > 0:
                self.all_terminated.wait()

    def hurry_and_stop(self):
        """
        Disabilita ulteriori submit() (che da questo momento sollevano
        SubmitDisabledException), poi fa terminare il prima possibile tutti i
        job gia' sottomessi ed esce quando tutti sono conclusi.

        Se i job ancora in coda sono piu' dei
        worker disponibili, vengono creati al volo dei worker aggiuntivi (fino a
        uno per ogni job in coda) cosi' da eseguirli tutti in parallelo invece
        di aspettare che si liberino i thread esistenti.
        """
        with self.lock:
            self.stopped = True
            # Un worker aggiuntivo per ogni job in coda che ecceda il numero
            # di worker gia' disponibili (se negativo, non se ne crea nessuno).
            nuovi_thread = len(self.coda_job) - len(self.workers)
            for _ in range(nuovi_thread):
                worker = Worker(self)
                self.workers.append(worker)
                worker.start()

            self.wait_for_termination()
