import time
import random
from queue import Queue
from threading import Thread, Lock, Condition, current_thread

# -------------------------- Utilità di log --------------------------

def _timestamp():
    return time.strftime("%H:%M:%S")


def stampa(msg):
    nome = current_thread().name
    print(f"[{_timestamp()}] [{nome}] {msg}")


# -------------------------- Classe Magazzino --------------------------

class Magazzino:
    def __init__(self, nome, inventario_iniziale=None):
        self.nome = nome
        self._inventario = dict(inventario_iniziale or {})
        self._lock = Lock()
        self._cond = Condition(self._lock)

        self._coda_arrivi = Queue()
        self._coda_uscite = Queue()

        self._threads = []
        self._config_attesa = True
        self._config_timeout = None
        self._ritardo_max = 0.4
        self._attivi = False

    def avvia_lavoratori(self, num_thread_arrivi=1, num_thread_uscite=1, attesa=True, timeout=None, ritardo_max=0.4):
        if self._attivi:
            return
        self._attivi = True
        self._config_attesa = attesa
        self._config_timeout = timeout
        self._ritardo_max = ritardo_max

        for i in range(num_thread_arrivi):
            t = Thread(target=self._loop_arrivi, name=f"{self.nome}-Arrivi-{i+1}")
            self._threads.append(t)
            t.start()

        for i in range(num_thread_uscite):
            t = Thread(target=self._loop_uscite, name=f"{self.nome}-Uscite-{i+1}")
            self._threads.append(t)
            t.start()

        stampa(f"[{self.nome}] Lavoratori avviati (arrivi={num_thread_arrivi}, uscite={num_thread_uscite}).")

    def ferma_lavoratori(self):
        if not self._attivi:
            return
        self._attivi = False
        num_arrivi = sum(1 for t in self._threads if "Arrivi" in t.name)
        num_uscite = sum(1 for t in self._threads if "Uscite" in t.name)
        stampa(f"[{self.nome}] Invio {num_arrivi} segnali di stop per thread arrivi")
        for _ in range(num_arrivi):
            self._coda_arrivi.put(None)
        stampa(f"[{self.nome}] Invio {num_uscite} segnali di stop per thread uscite")
        for _ in range(num_uscite):
            self._coda_uscite.put(None)
        stampa(f"[{self.nome}] Tutti i segnali di stop inviati")

    def attendi_terminazione(self):
        stampa(f"[{self.nome}] Inizio attesa terminazione...")
        stampa(f"[{self.nome}] Thread attivi: {len(self._threads)}")
        
        stampa(f"[{self.nome}] Dimensione coda_arrivi: {self._coda_arrivi.qsize()}")
        stampa(f"[{self.nome}] Dimensione coda_uscite: {self._coda_uscite.qsize()}")
        
        # Prima aspettiamo che le code siano vuote
        stampa(f"[{self.nome}] Attendo che coda_arrivi sia vuota (join)...")
        self._coda_arrivi.join()
        stampa(f"[{self.nome}] Coda arrivi completa!")
        
        stampa(f"[{self.nome}] Attendo che coda_uscite sia vuota (join)...")
        self._coda_uscite.join()
        stampa(f"[{self.nome}] Coda uscite completa!")
        
        # Poi aspettiamo che i thread terminino
        stampa(f"[{self.nome}] Attendo join di {len(self._threads)} thread...")
        for i, t in enumerate(self._threads):
            stampa(f"[{self.nome}] Join thread {i+1}/{len(self._threads)}: {t.name} (alive: {t.is_alive()})")
            t.join()
            stampa(f"[{self.nome}] Thread {t.name} terminato")
        
        stampa(f"[{self.nome}] Attendi terminazione completato!")

    def inserisci_arrivo(self, articolo, quantità):
        self._coda_arrivi.put((articolo, quantità))

    def inserisci_uscita(self, articolo, quantità):
        self._coda_uscite.put((articolo, quantità))

    def stato(self):
        with self._lock:
            return dict(self._inventario)

    def _aggiungi(self, articolo, quantità):
        if quantità <= 0:
            return
        with self._lock:
            precedente = self._inventario.get(articolo, 0)
            self._inventario[articolo] = precedente + quantità
            nuovo = self._inventario[articolo]
            stampa(f"[{self.nome}] Aggiunte {quantità} unità di '{articolo}'. Totale: {nuovo}.")
            self._cond.notify_all()

    def _preleva(self, articolo, quantità):
        if quantità <= 0:
            return True
        attesa = self._config_attesa
        timeout = self._config_timeout

        with self._lock:
            if not attesa:
                disponibile = self._inventario.get(articolo, 0)
                da_prelevare = min(disponibile, quantità)
                self._inventario[articolo] = disponibile - da_prelevare
                stampa(f"[{self.nome}] Prelievo NON bloccante {da_prelevare}/{quantità} di '{articolo}'. Rimanenza: {self._inventario.get(articolo, 0)}.")
                return da_prelevare == quantità

            termine = None if timeout is None else (time.monotonic() + timeout)
            while self._inventario.get(articolo, 0) < quantità:
                rimanente = None if termine is None else max(0.0, termine - time.monotonic())
                if termine is not None and rimanente == 0.0:
                    stampa(f"[{self.nome}] Timeout in attesa di {quantità} unità di '{articolo}'. Disponibili: {self._inventario.get(articolo, 0)}.")
                    return False
                stampa(f"[{self.nome}] Attendo disponibilità: servono {quantità} di '{articolo}', ora ce ne sono {self._inventario.get(articolo, 0)}...")
                self._cond.wait(timeout=rimanente)

            self._inventario[articolo] -= quantità
            stampa(f"[{self.nome}] Prelevate {quantità} unità di '{articolo}'. Rimanenza: {self._inventario.get(articolo, 0)}.")
            return True

    def _loop_arrivi(self):
        stampa(f"[{self.nome}] Lavoratore arrivi iniziato")
        while True:
            stampa(f"[{self.nome}] Lavoratore arrivi: attendo item dalla coda...")
            ordine = self._coda_arrivi.get()
            stampa(f"[{self.nome}] Lavoratore arrivi: ricevuto item: {ordine}")
            if ordine is None:
                stampa(f"[{self.nome}] Ricevuto segnale di stop. Chiamo task_done e termino.")
                self._coda_arrivi.task_done()
                stampa(f"[{self.nome}] task_done chiamato, esco dal loop")
                break
            articolo, quantità = ordine
            time.sleep(random.uniform(0.0, self._ritardo_max))
            self._aggiungi(articolo, quantità)
            stampa(f"[{self.nome}] Chiamo task_done per ordine {articolo}")
            self._coda_arrivi.task_done()
        stampa(f"[{self.nome}] Lavoratore arrivi terminato")

    def _loop_uscite(self):
        stampa(f"[{self.nome}] Lavoratore uscite iniziato")
        while True:
            stampa(f"[{self.nome}] Lavoratore uscite: attendo item dalla coda...")
            ordine = self._coda_uscite.get()
            stampa(f"[{self.nome}] Lavoratore uscite: ricevuto item: {ordine}")
            if ordine is None:
                stampa(f"[{self.nome}] Ricevuto segnale di stop. Chiamo task_done e termino.")
                self._coda_uscite.task_done()
                stampa(f"[{self.nome}] task_done chiamato, esco dal loop")
                break
            articolo, quantità = ordine
            time.sleep(random.uniform(0.0, self._ritardo_max))
            esito = self._preleva(articolo, quantità)
            if not esito:
                stampa(f"[{self.nome}] Ordine non evaso per '{articolo}' (richiesti {quantità}).")
            stampa(f"[{self.nome}] Chiamo task_done per ordine {articolo}")
            self._coda_uscite.task_done()
        stampa(f"[{self.nome}] Lavoratore uscite terminato")


# -------------------------- Esempio d'uso --------------------------

if __name__ == "__main__":
    stampa("=== MAIN: Creazione magazzini ===")
    m1 = Magazzino("MondoConveniente", {
        "Laptop Smell XPS 13": 50,
        "Smartphone oPhone 14": 80,
        "Console PrayStation 5": 40,
        "Libro Python Avanzato": 120
    })

    m2 = Magazzino("Alibaba'", {
        "Tablet oPad Pro": 30,
        "Cuffie Biose QC45": 60,
        "Monitor GL UltraFine": 25,
        "Laptop Renovo ThonkPad": 40
    })

    stampa("=== MAIN: Avvio lavoratori ===")
    #m1.avvia_lavoratori(num_thread_arrivi=3, num_thread_uscite=3, attesa=True)
    m2.avvia_lavoratori(num_thread_arrivi=2, num_thread_uscite=2, attesa=False)

    # Genera ordini casuali basandosi sugli articoli presenti nei magazzini
    stampa("=== MAIN: Generazione ordini ===")
    '''
    for _ in range(200):
        art = random.choice(list(m1.stato().keys()))
        qta = random.randint(10, 100)
        m1.inserisci_arrivo(art, qta)
    for _ in range(200):
        art = random.choice(list(m1.stato().keys()))
        qta = random.randint(5, 120)
        m1.inserisci_uscita(art, qta)
    '''
    stampa("=== MAIN: Inserimento arrivi m2 ===")
    for _ in range(150):
        art = random.choice(list(m2.stato().keys()))
        qta = random.randint(5, 80)
        m2.inserisci_arrivo(art, qta)
    stampa("=== MAIN: Inserimento uscite m2 ===")
    for _ in range(150):
        art = random.choice(list(m2.stato().keys()))
        qta = random.randint(5, 100)
        m2.inserisci_uscita(art, qta)

    stampa("=== MAIN: Sleep 5 secondi ===")
    time.sleep(5.0)

    stampa("=== MAIN: Fermo lavoratori ===")
    #m1.ferma_lavoratori()
    m2.ferma_lavoratori()

    stampa("=== MAIN: Attendo terminazione m2 ===")
    #m1.attendi_terminazione()
    m2.attendi_terminazione()

    stampa("=== MAIN: Terminazione completata ===")
    stampa("Stato finale dei magazzini:")
    for m in (m1, m2):
        print(f"  >> {m.nome}")
        for articolo, qta in sorted(m.stato().items()):
            print(f"     - {articolo}: {qta}")
