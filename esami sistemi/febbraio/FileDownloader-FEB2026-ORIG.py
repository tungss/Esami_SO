import random
import string
import time
from threading import Thread, Lock, Condition


# -----------------------------
# Dati e "server" simulato
# -----------------------------

class FintoServer:
    """
    Server finto: genera un file casuale e risponde con una latenza casuale quando un certo 
    pezzettone viene richiesto per il 'download' simulato. I pezzettoni non sono materializzati, 
    ma estratti on-the-fly come sottostringhe del 'file' di partenza.
    """
    # num_pezzettoni: intero, numero di pezzettoni in cui dividere il file
    # lunghezza_file: intero, lunghezza totale del file da generare
    def __init__(self, num_pezzettoni, lunghezza_file):
        # Genera seed da /dev/urandom (SystemRandom)
        sys_random = random.SystemRandom()
        seed_file = sys_random.randint(0, 2**32 - 1)
        seed_latenza = sys_random.randint(0, 2**32 - 1)
        
        self._rng_latenza = random.Random(seed_latenza)
        
        # Genera il file random
        rng_file = random.Random(seed_file)
        alfabeto = string.ascii_letters + string.digits + " _-.,;:!?()[]{}"
        self._testo_originale = "".join(rng_file.choice(alfabeto) for _ in range(lunghezza_file))
        
        # Salva parametri per calcolo pezzettoni on-the-fly
        self._num_pezzettoni = num_pezzettoni
        self._lunghezza_file = lunghezza_file
        self._dimensione_pezzettone = lunghezza_file // num_pezzettoni + (1 if lunghezza_file % num_pezzettoni else 0)

    # Restituisce il numero totale di pezzettoni (intero)
    def numero_pezzettoni(self):
        return self._num_pezzettoni

    # index: intero, indice del pezzettone da scaricare
    # Restituisce: stringa contenente il pezzettone
    def download_pezzettone(self, index):
        time.sleep(self._rng_latenza.uniform(0.5, 3.0))  # latenza simulata
        
        # Calcola gli indici per estrarre la sottostringa
        start = index * self._dimensione_pezzettone
        end = min(start + self._dimensione_pezzettone, self._lunghezza_file)
        
        return self._testo_originale[start:end]
    
    # Restituisce il testo originale completo (stringa) per verifica
    def get_testo_originale(self):
        return self._testo_originale


# -----------------------------
# Coda task
# -----------------------------

class TaskQueue:
    def __init__(self):
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._tasks = []  # lista di interi (indici dei pezzettoni)
        self._closed = False

    # index: intero, indice del pezzettone da aggiungere alla coda
    def put(self, index):
        with self._lock:
            if self._closed:
                raise RuntimeError("TaskQueue chiusa")
            self._tasks.append(index)
            self._cond.notify_all()

    # Chiude la coda, nessun parametro
    def close(self):
        with self._lock:
            self._closed = True
            self._cond.notify_all()

    # Restituisce un intero (indice) o None se la coda è chiusa e vuota
    def get(self):
        with self._lock:
            while not self._tasks and not self._closed:
                self._cond.wait()

            if self._tasks:
                return self._tasks.pop(0)

            return None


# -----------------------------
# Worker e Assembler
# -----------------------------
# Un worker thread scarica dei pezzettoni di file dal server: legge quale pezzettone prendere dalla TaskQueue
# poi procede allo scaricamento e infine salva il risultato nel DownloadManagerSimulato.
# L'assembler thread invece legge i pezzettoni scaricati in ordine e li scrive sul file di output.
#
class Worker(Thread):
    # worker_id: intero, identificativo del worker
    # server: FintoServer, il server da cui scaricare
    # task_queue: TaskQueue, la coda dei task
    # manager: DownloadManagerSimulato, il manager che coordina tutto
    def __init__(self, worker_id, server, task_queue, manager):
        super().__init__(name=f"worker-{worker_id}", daemon=True)
        self._server = server
        self._task_queue = task_queue
        self._manager = manager

    def run(self):
        while True:
            index = self._task_queue.get()
            # Se la coda è chiusa e vuota, esci
            if index is None:
                return

            pezzettone = self._server.download_pezzettone(index)
            self._manager.store_pezzettone(index, pezzettone)


class Assembler(Thread):
    # output_path: stringa, percorso del file di output
    # totale_pezzettoni: intero, numero totale di pezzettoni da assemblare
    # manager: DownloadManagerSimulato, il manager che coordina tutto
    def __init__(self, output_path, totale_pezzettoni, manager):
        super().__init__(name="assembler", daemon=True)
        self._output_path = output_path
        self._totale_pezzettoni = totale_pezzettoni
        self._manager = manager

    #
    # L'assemblatore rimette insieme il file. Nota che la scrittura su file deve essere nell'ordine corretto
    # quindi aspetta che ogni pezzettone sia disponibile prima di scriverlo.
    #
    def run(self):
        next_index = 0

        with open(self._output_path, "w", encoding="utf-8") as f:
            while next_index < self._totale_pezzettoni:
                pezzettone = self._manager.get_next_pezzettone_pronto(next_index)
                f.write(pezzettone)
                next_index += 1


# -----------------------------
# Monitor thread
# -----------------------------

class ProgressMonitor(Thread):
    # totale_pezzettoni: intero, numero totale di pezzettoni
    # manager: DownloadManagerSimulato, il manager che coordina tutto
    # refresh_interval: float, intervallo di aggiornamento in secondi (default 0.1)
    def __init__(self, totale_pezzettoni, manager, refresh_interval=0.1):
        super().__init__(name="progress-monitor", daemon=True)
        self._totale_pezzettoni = totale_pezzettoni
        self._manager = manager
        self._refresh_interval = refresh_interval
        self._stopped = False

    # Ferma il monitor
    def stop_monitor(self):
        self._stopped = True

    def run(self):
        while not self._stopped:
            scaricati = self._manager.get_stato()
            
            # Costruisci la barra di progresso: un carattere per pezzettone
            if self._totale_pezzettoni <= 80:
                bar = ['*' if i in scaricati else '-' for i in range(self._totale_pezzettoni)]
                posizioni_complete = len(scaricati)
                pezzettoni_visualizzati = self._totale_pezzettoni
            else:
                # Campiona 80 pezzettoni distribuiti
                step = self._totale_pezzettoni / 80
                bar = ['*' if int(i * step) in scaricati else '-' for i in range(80)]
                posizioni_complete = bar.count('*')
                pezzettoni_visualizzati = 80
            
            # Mostra la barra
            progress_str = "".join(bar)
            percentage = posizioni_complete / pezzettoni_visualizzati * 100
            print(f"\r[{progress_str}] {len(scaricati)}/{self._totale_pezzettoni} ({percentage:.1f}%)", end="", flush=True)
            
            # Se completato, esci
            if len(scaricati) >= self._totale_pezzettoni:
                # Stampa 100% prima di uscire
                print(f"\r[{'*' * len(bar)}] {self._totale_pezzettoni}/{self._totale_pezzettoni} (100.0%)")
                break
            
            time.sleep(self._refresh_interval)


# -----------------------------
# Manager
# -----------------------------

class DownloadManagerSimulato:
    # server: FintoServer, il server da cui scaricare
    # output_path: stringa, percorso del file di output
    # worker_count: intero, numero di worker da usare
    def __init__(self, server, output_path, worker_count):
        self._server = server
        self._output_path = output_path
        self._worker_count = worker_count

        self._task_queue = TaskQueue()

        self._result_lock = Lock()
        self._result_cond = Condition(self._result_lock)
        self._results = {}  # dizionario: int -> stringa
        self._pezzettoni_scaricati = set()  # set di interi

    # Memorizza un pezzettone scaricato e notifica gli observer
    def store_pezzettone(self, index, pezzettone):
        with self._result_lock:
            self._results[index] = pezzettone
            self._pezzettoni_scaricati.add(index)
            self._result_cond.notify_all()

    # Estrae il pezzettone con indice dato, aspettando se necessario che sia pronto
    def get_next_pezzettone_pronto(self, index):
        with self._result_lock:
            while index not in self._results:
                self._result_cond.wait()
            return self._results.pop(index)

    # Restituisce un bitset (set) dei pezzettoni scaricati per la visualizzazione
    def get_stato(self):
        with self._result_lock:
            return self._pezzettoni_scaricati.copy()

    # Esegue il download e l'assemblaggio
    def esegui(self):
        total = self._server.numero_pezzettoni()

        assembler = Assembler(
            output_path=self._output_path,
            totale_pezzettoni=total,
            manager=self,
        )

        monitor = ProgressMonitor(
            totale_pezzettoni=total,
            manager=self,
        )

        workers = [
            Worker(
                worker_id=i,
                server=self._server,
                task_queue=self._task_queue,
                manager=self,
            )
            for i in range(self._worker_count)
        ]

        assembler.start()
        monitor.start()
        for w in workers:
            w.start()

        for i in range(total):
            self._task_queue.put(i)

        self._task_queue.close()

        for w in workers:
            w.join()

        with self._result_lock:
            self._result_cond.notify_all()

        assembler.join()
        monitor.stop_monitor()
        monitor.join()


# -----------------------------
# Demo + verifica
# -----------------------------

server = FintoServer(num_pezzettoni=80, lunghezza_file=10_000)

output_path = "file_riassemblato.txt"
manager = DownloadManagerSimulato(server, output_path, worker_count=6)

#
# Nota che il manager non è un thread a parte, quindi esegui in realtà si svolge nel thread principale
#
manager.esegui()

print("Download simulato completato.")
