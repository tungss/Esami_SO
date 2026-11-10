from threading import Lock, Condition, Thread
import random
import time

#
# INCROCIO
#
# Un incrocio a quattro strade (Nord, Sud, Est, Ovest) e' diviso in quattro quadranti:
#
#              N
#         +---------+
#         |  NO| NE |
#    O    |----+----|    E
#         |  SO| SE |
#         +---------+
#              S
#
# Ogni Auto e' un thread che arriva all'incrocio da una delle quattro direzioni
# (provenienza) e deve attraversarlo per svoltare a destra, proseguire dritto,
# oppure svoltare a sinistra. Per farlo deve lockare TUTTI i quadranti che il suo
# percorso attraversa, tenerli occupati per il tempo di attraversamento, e poi
# rilasciarli. Un quadrante puo' essere occupato da una sola auto alla volta.
#
# Quadranti necessari in base alla manovra (guida a destra, come in Italia):
#   - destra   -> 1 quadrante  (solo quello di ingresso)
#   - dritto   -> 2 quadranti  (quello di ingresso e quello attraversato in linea retta)
#   - sinistra -> 3 quadranti  (l'auto "spazza" quasi tutto l'incrocio)
#
# L'incrocio e' protetto in maniera simile all'esempio dei cinque filosofi. 
# Lo stato di occupazione e' rappresentato da un booleano per
# quadrante (libero/occupato). Un'auto che vuole attraversare chiama
# impegna_incrocio() indicando che manovra vuole fare: il
# metodo, dopo avere impegnato big_lock, controlla se i quadranti che servono 
# sono TUTTI liberi insieme e, solo in
# quel caso, li marca come occupati; altrimenti si aspetta (wait sulla
# Condition associata a big_lock) e si riprova al prossimo risveglio. Poiche'
# il controllo e la prenotazione di tutti i quadranti avvengono in un'unica
# sezione protetta dallo stesso lock, non serve nessun ordine di acquisizione: non si
# puo' mai verificare l'attesa circolare tipica del deadlock (nessuna auto
# tiene "a meta'" un sottoinsieme dei quadranti che le servono).
#

PROVENIENZE = ['N', 'S', 'E', 'O']
SVOLTE = ['destra', 'dritto', 'sinistra']
QUADRANTI = ['NE', 'NO', 'SE', 'SO']

#
#              N
#         +---------+
#         |  NO| NE |
#    O    |----+----|    E
#         |  SO| SE |
#         +---------+
#              S

# Percorso (elenco di quadranti) in funzione di (provenienza, svolta).
PERCORSI = {
        ('N', 'destra'):   ['NO'],
        ('N', 'dritto'):   ['NO', 'SO'],
        ('N', 'sinistra'): ['NO', 'SO', 'SE'],

        ('S', 'destra'):   ['SE'],
        ('S', 'dritto'):   ['SE', 'NE'],
        ('S', 'sinistra'): ['SE', 'NE', 'NO'],

        ('E', 'destra'):   ['NE'],
        ('E', 'dritto'):   ['NE', 'NO'],
        ('E', 'sinistra'): ['NE', 'NO', 'SO'],

        ('O', 'destra'):   ['SO'],
        ('O', 'dritto'):   ['SO', 'SE'],
        ('O', 'sinistra'): ['SO', 'SE', 'NE'],
    }



# ---------------------------------------------------------------------------
# Incrocio
# ---------------------------------------------------------------------------

class Incrocio:


    _MAX_LOG = 8  # righe di log mostrate nella dashboard (modalita' non continua)

    def __init__(self):
        self.big_lock = Lock()
        self.cond_incrocio = Condition(self.big_lock)
        #
        # un booleano per quadrante: True = libero, False = occupato.
        #
        self.libero = {q: True for q in QUADRANTI}
        #
        # occupanti e _log sono protetti anch'essi da big_lock
        #         
        self.occupanti = {q: None for q in QUADRANTI}
        self._log = []          # tutti i messaggi di log, dall'inizio della simulazione
        self._log_stampati = 0  # quanti messaggi sono gia' stati stampati in modalita' continua

    
    #
    # Restituisce l'elenco dei quadranti necessari per attraversare l'incrocio in base alla provenienza e alla svolta.
    #
    # Esempio: quadranti_necessari('N', 'sinistra') -> ['NO', 'SO', 'SE']
    #
    # (Entro nel quadrante NO, poi attraversando l'incrocio passo in SO e infine svolto in SE)
    #
    def quadranti_necessari(self, provenienza, svolta):
        return PERCORSI[(provenienza, svolta)]

    def attraversa(self, auto):
        """
        Impegna i quadranti necessari alla manovra di 'auto' (bloccandosi finche'
        non sono tutti liberi insieme), simula l'attraversamento e infine li
        rilascia.
        """
        quadranti = self.quadranti_necessari(auto.provenienza, auto.svolta)

        self.log(f"Auto#{auto.id} ({auto.provenienza}->{auto.svolta}) in attesa di bloccare {quadranti}")

        self.impegna_incrocio(quadranti)
        self._segna_occupati(quadranti, auto.id)
        self.log(f"Auto#{auto.id} ({auto.provenienza}->{auto.svolta}) attraversa {quadranti}")
        self.tempo_che_simula_attraversamento()
        self._segna_occupati(quadranti, None)
        self.rilascia_incrocio(quadranti)

        self.log(f"Auto#{auto.id} ({auto.provenienza}->{auto.svolta}) ha lasciato l'incrocio")

    def impegna_incrocio(self, quadranti):
        """
        Bloccante: attende finche' tutti i quadranti richiesti non sono liberi
        CONTEMPORANEAMENTE, poi li marca come occupati in un'unica sezione
        critica (nessun altro thread puo' intromettersi tra il controllo e la
        prenotazione, perche' entrambi avvengono sotto lo stesso big_lock).
        """
        with self.big_lock:
            while not all(self.libero[q] for q in quadranti):
                self.cond_incrocio.wait()
            for q in quadranti:
                self.libero[q] = False

    def rilascia_incrocio(self, quadranti):
        """Libera i quadranti occupati e risveglia le auto in attesa."""
        with self.big_lock:
            for q in quadranti:
                self.libero[q] = True
            self.cond_incrocio.notify_all()

    def tempo_che_simula_attraversamento(self):
        time.sleep(random.uniform(0.5, 1.5))

    def _segna_occupati(self, quadranti, auto_id):
        with self.big_lock:
            for q in quadranti:
                self.occupanti[q] = auto_id

    def log(self, msg):
        with self.big_lock:
            self._log.append(msg)

    def stampa_stato(self, continuo=False):
        """
        Mostra lo stato corrente dell'incrocio. Due modalita':
          - continuo=False (default): dashboard che si ridisegna da capo ad ogni
            chiamata (cancella lo schermo), con la griglia dei quadranti e le
            ultime _MAX_LOG righe di log.
          - continuo=True: non cancella mai lo schermo e non ridisegna la griglia;
            stampa solo le righe di log aggiunte dall'ultima chiamata, una sotto
            l'altra, cosi' si puo' scorrere tutta la cronologia degli eventi.
        """
        # Prende big_lock, stampa (leggendo occupanti/log direttamente, senza
        # copiarli prima), e lo rilascia: niente lock separato per il display.
        with self.big_lock:
            if continuo:
                righe_nuove = self._log[self._log_stampati:]
                self._log_stampati = len(self._log)
                for m in righe_nuove:
                    print(m, flush=True)
                return

            def cella(q):
                auto_id = self.occupanti[q]
                testo = f"Auto#{auto_id}" if auto_id is not None else "libero"
                return testo.center(9)

            righe_nuove = self._log[-self._MAX_LOG:]
            righe = [
                f"                 N",
                f"          +---------+---------+",
                f"          |{cella('NO')}|{cella('NE')}|",
                f"     O    +---------+---------+    E",
                f"          |{cella('SO')}|{cella('SE')}|",
                f"          +---------+---------+",
                f"                 S",
                f"",
                f"LOG:",
            ]
            righe += [f"  {m}" for m in righe_nuove]

            # "\033[2J" e "\033[H" sono codici ANSI (sequenze di escape interpretate dal terminale,
            # non caratteri stampati): il primo codice cancella tutto lo schermo, il secondo riporta
            # il cursore in alto a sinistra. Le usiamo insieme per ridisegnare la dashboard da capo
            # a ogni refresh invece di accumulare stampe una sotto l'altra.
            print("\033[2J\033[H" + "\n".join(righe), flush=True)


# ---------------------------------------------------------------------------
# Auto
# ---------------------------------------------------------------------------

class Auto(Thread):
    _contatore = 0
    #
    # Lock a protezione del contatore che assegna l'id a ogni auto nuova
    #
    _lock_id = Lock()

    def __init__(self, incrocio, provenienza, svolta):
        super().__init__()
        with Auto._lock_id:
            Auto._contatore += 1
            self.id = Auto._contatore
        self.incrocio = incrocio
        # Lato dell'incrocio da cui si proviene
        self.provenienza = provenienza
        # Intenzione di svolta
        self.svolta = svolta

    def run(self):
        self.incrocio.attraversa(self)


# ---------------------------------------------------------------------------
# VisualizzatoreIncrocio - thread che ridisegna periodicamente lo stato dell'incrocio
# ---------------------------------------------------------------------------

class VisualizzatoreIncrocio(Thread):
    def __init__(self, incrocio, intervallo=0.5, continuo=False):
        super().__init__()
        self.incrocio = incrocio
        self.intervallo = intervallo
        self.continuo = continuo
        self.lock = Lock()
        self.attivo = True

    def run(self):
        while True:
            with self.lock:
                if not self.attivo:
                    break
            self.incrocio.stampa_stato(continuo=self.continuo)
            time.sleep(self.intervallo)

    def ferma(self):
        with self.lock:
            self.attivo = False


# ---------------------------------------------------------------------------
# Main di prova
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    N_AUTO = 97

    incrocio = Incrocio()

    # Passa continuo=True per una stampa a flusso continuo (nessuna cancellazione
    # dello schermo, solo le righe di log nuove ad ogni refresh) invece della
    # dashboard con griglia dei quadranti.
    visualizzatore = VisualizzatoreIncrocio(incrocio, continuo=False)
    visualizzatore.start()

    auto = [
        Auto(incrocio, random.choice(PROVENIENZE), random.choice(SVOLTE))
        for _ in range(N_AUTO)
    ]
    for a in auto:
        a.start()
        time.sleep(random.uniform(0.1, 0.4))  # arrivi scaglionati nel tempo

    for a in auto:
        a.join()

    visualizzatore.ferma()
    visualizzatore.join()

    print("Simulazione terminata: tutte le auto hanno attraversato l'incrocio.")
