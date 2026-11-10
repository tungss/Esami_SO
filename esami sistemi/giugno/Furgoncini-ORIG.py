from threading import Condition, Lock, Thread
import random
import time

# Nota su  C = list(L)
# Restituisce una copia superficiale (shallow copy) della lista L e la pone in C.
# Es.   a = [1, 2, 3];  b = list(a)   =>  b e' una nuova lista allocata in una porzione di memoria differente,
#  ma con gli stessi elementi;
#       modificare la lista b (append, remove, ...) non altera a, e viceversa.
# In questo file usiamo questa cosa per "fotografare" una lista condivisa mentre si tiene il lock,
# cosi' da poter iterare sulla copia senza mantenere il lock durante l'elaborazione.

#
# FURGONCINI
#
# Quattro sedi di magazzini (A, B, C, D) sono collegate in anello circolare:
#
#   A --> B --> C --> D
#   ^                |
#   +----------------+
#
# Ogni sede ha tre componenti:
#   Garage_arrivi    : buffer limitato di furgoncini appena arrivati (produttore: Guidatore,
#                      consumatore: Lavoratore)
#   BufferTemporaneo : deposito dei pacchi in transito (alimentato dai Lavoratori durante lo
#                      scarico e dai ProduttoriPacchi; svuotato dai Lavoratori durante il carico)
#   Garage_partenze  : buffer limitato di furgoncini caricati e pronti a partire
#                      (produttore: Lavoratore, consumatore: Guidatore)
#
# Ciclo di vita di un furgoncino:
#   1. Il Guidatore A->B deposita il furgoncino nel Garage_arrivi di B.
#   2. Un Lavoratore di B preleva il furgoncino dal Garage_arrivi.
#   3. Il furgoncino viene scaricato pacco per pacco: i pacchi destinati a B vengono consegnati,
#      quelli con altra destinazione finiscono nel BufferTemporaneo di B.
#   4. Il furgoncino vuoto viene ricaricato: si prelevano pacchi dal BufferTemporaneo fino a esaurire lo spazio disponibile
#      (il furgoncino parte comunque dopo un certo tempo se non ci sono pacchi).
#   5. Il Lavoratore deposita il furgoncino caricato nel Garage_partenze di B.
#   6. Il Guidatore B->C lo preleva e parte per la sua destinazione.
#

SEDI = ['A', 'B', 'C', 'D']


def get_sede_successiva(nome):
    return SEDI[(SEDI.index(nome) + 1) % len(SEDI)]


# ---------------------------------------------------------------------------
# Pacco
# ---------------------------------------------------------------------------

class Pacco:
    def __init__(self, dimensione, mittente, destinatario):
        self.dimensione = dimensione    # "peso" del pacco, usato per verificare la capienza
        self.mittente = mittente        # nome sede mittente  ('A'..'D')
        self.destinatario = destinatario  # nome sede destinataria ('A'..'D')

    def __repr__(self):
        # il metodo __repr__ e' chiamato automaticamente quando si stampa l'oggetto. Equivale al toString di Java.
        # es. p = Pacco(3, 'A', 'C')
        # print(p)  =>  "Pacco(3kg A->C)"
        return f"Pacco({self.dimensione}kg {self.mittente}->{self.destinatario})"


# ---------------------------------------------------------------------------
# Furgoncino
# ---------------------------------------------------------------------------

class Furgoncino:
    #
    # _contatore e _lock_id sono attributi di classe (statici): esistono una sola volta
    # condivisa da tutte le istanze di furgoncino. Piu' thread possono creare Furgoncini contemporaneamente,
    # quindi l'incremento di _contatore (leggi-incrementa-scrivi) va protetto da una race condition.
    # _lock_id garantisce che ogni Furgoncino riceva un id univoco anche in presenza di concorrenza.
    # es. senza lock: due thread possono leggere _contatore==5 contemporaneamente e assegnare entrambi id=6.
    #
    _contatore = 0
    _lock_di_classe = Lock()

    def __init__(self, capacita_max):
        with Furgoncino._lock_di_classe:
            Furgoncino._contatore += 1
            self.id = Furgoncino._contatore
        self.capacita_max = capacita_max   # dimensione totale massima caricabile
        self.pacchi = []
        self.spazio_disponibile = self.capacita_max
        self._lock = Lock()

    def preleva_pacco(self):
        """
            Preleva il primo pacco (FIFO). Restituisce None se il furgoncino e' vuoto.
            Nota che questo prelievo non è bloccante: se il furgoncino è vuoto, restituisce subito None invece di aspettare che arrivi un pacco.
        """
        with self._lock:
            self.spazio_disponibile += self.pacchi[0].dimensione if self.pacchi else 0
            return self.pacchi.pop(0) if self.pacchi else None

    # deve fallire qualora il pacco non entri.
    def deposita_pacco(self, pacco):
        """Deposita un pacco nel furgoncino. Operazione che può fallire se il pacco non entra (dimensione maggiore dello spazio disponibile)."""
        with self._lock:
            if self.spazio_disponibile >= pacco.dimensione:
                self.pacchi.append(pacco)
                self.spazio_disponibile -= pacco.dimensione
                return True
            else:
                return False

    def __repr__(self):
        # il metodo __repr__ e' chiamato automaticamente quando si stampa l'oggetto
        # es. f = Furgoncino(20)   print(f)  =>  "Furgoncino#1(0/20kg)"
        return f"Furgoncino#{self.id}({self.capacita_max - self.spazio_disponibile}/{self.capacita_max}kg)"


# ---------------------------------------------------------------------------
# BufferBloccante  -  buffer FIFO thread-safe, opzionalmente limitato
# ---------------------------------------------------------------------------

class BufferBloccante:
    """
    Buffer FIFO thread-safe.
    - capacita_max=None (default): illimitato, deposita() non blocca mai.
    - capacita_max=N: deposita() blocca il produttore quando ci sono N elementi.
    preleva() blocca sempre il consumatore finche' il buffer e' vuoto.
    """
    def __init__(self, capacita_max=None):
        self.capacita_max = capacita_max
        self.elementi = []
        self.lock = Lock()
        self.non_vuoto = Condition(self.lock)
        self.non_pieno = Condition(self.lock)

    def deposita(self, elemento):
        """Deposita un elemento. Blocca se il buffer e' pieno (solo se limitato)."""
        with self.lock:
            while self.capacita_max is not None and len(self.elementi) >= self.capacita_max:
                self.non_pieno.wait()
            self.elementi.append(elemento)
            self.non_vuoto.notify_all()

    def preleva(self, timeout=None):
        """Preleva il primo elemento (FIFO). Blocca se il buffer e' vuoto. Timeout opzionale"""
        with self.lock:
            while not self.elementi:
                self.non_vuoto.wait(timeout=timeout)
            if self.elementi:
                elemento = self.elementi.pop(0)
                self.non_pieno.notify_all()
                return elemento
        return None


# ---------------------------------------------------------------------------
# Sede
# ---------------------------------------------------------------------------

class Sede:
    def __init__(self, nome, cap_arrivi, cap_partenze):
        self.nome = nome
        self.garage_arrivi   = BufferBloccante(cap_arrivi)
        self.buffer_temporaneo = BufferBloccante()          # illimitato
        self.garage_partenze = BufferBloccante(cap_partenze)

    def __repr__(self):
        # il metodo __repr__ e' chiamato automaticamente quando si stampa l'oggetto
        # es. s = Sede('B', 3, 2)   print(s)  =>  "Sede(B)"
        return f"Sede({self.nome})"


# ---------------------------------------------------------------------------
# TrattaStradale
# ---------------------------------------------------------------------------

class TrattaStradale:
    """
    Rappresenta la tratta tra due sedi adiacenti e tiene traccia, sotto lock,
    dei furgoncini attualmente in viaggio e dei guidatori che rientrano a piedi.

    Il lock permette a Display._snapshot() di leggere uno stato coerente:
    tutti i campi vengono letti insieme mentre il lock e' acquisito,
    evitando di osservare aggiornamenti parziali tra una lettura e l'altra.
    """
    def __init__(self, sede_da, sede_a):
        self.sede_da = sede_da
        self.sede_a  = sede_a
        self.lock = Lock()
        self.furgoncini_in_viaggio = []
        self.n_guidatori_in_rientro = 0

    def preleva_e_parte(self):
        """
        Preleva un furgoncino da sede_da.garage_partenze e lo registra in viaggio sulla tratta
        in un'unica sezione sincronizzata: il furgoncino non e' mai invisibile allo snapshot.
        Ordine dei lock: garage_partenze.lock -> self.lock  (stesso ordine di Display._snapshot)
        """
        garage = self.sede_da.garage_partenze
        with garage.lock:
            while not garage.elementi:
                garage.non_vuoto.wait()
            with self.lock:                                # tratta.lock: sempre dopo garage.lock (stesso ordine di _snapshot)
                furgoncino = garage.elementi.pop(0)
                garage.non_pieno.notify_all()
                self.furgoncini_in_viaggio.append(furgoncino)
        return furgoncino

    def deposita_e_arriva(self, furgoncino):
        """
        Deposita il furgoncino in sede_a.garage_arrivi e lo rimuove dalla tratta
        in un'unica sezione sincronizzata: il furgoncino non e' mai invisibile allo snapshot.
        Ordine dei lock: garage_arrivi.lock -> self.lock  (stesso ordine di Display._snapshot)
        """
        garage = self.sede_a.garage_arrivi
        with garage.lock:
            while (garage.capacita_max is not None and
                   len(garage.elementi) >= garage.capacita_max):
                garage.non_pieno.wait()
            with self.lock:                                # tratta.lock: sempre dopo garage.lock (stesso ordine di _snapshot)
                garage.elementi.append(furgoncino)
                garage.non_vuoto.notify_all()
                self.furgoncini_in_viaggio.remove(furgoncino)

    def guidatore_parte_a_piedi(self):
        with self.lock:
            self.n_guidatori_in_rientro += 1

    def guidatore_arrivato(self):
        with self.lock:
            self.n_guidatori_in_rientro -= 1


# ---------------------------------------------------------------------------
# Lavoratore
# ---------------------------------------------------------------------------

class Lavoratore(Thread):
    """
    Opera continuamente presso la propria sede:
      1. Preleva un furgoncino dal Garage_arrivi.
      2. Scarica il furgoncino pacco per pacco:
           - pacco.destinatario == sede.nome  ->  consegnato (rimosso dal sistema)
           - altrimenti                        ->  depositato nel BufferTemporaneo
      3. Carica il furgoncino prendendo pacchi dal BufferTemporaneo
         fino a riempire lo spazio disponibile (attende se il buffer e' vuoto).
      4. Deposita il furgoncino caricato nel Garage_partenze.
    """
    def __init__(self, sede, display):
        super().__init__()
        self.sede = sede
        self.display = display

    def _scarica(self, furgoncino):
        while True:
            pacco = furgoncino.preleva_pacco()
            if pacco is None:
                break
            if pacco.destinatario == self.sede.nome:
                self.display.log(f"[{self.sede.nome}] Consegnato {pacco}")
            else:
                self.sede.buffer_temporaneo.deposita(pacco)

    def _carica(self, furgoncino):
        #
        # prende un pacco dal buffer temporaneo e prova a metterlo nel furgoncino, se non ci sta lo rimette nel buffer
        # se non arrivano pacchi da caricare, il furgoncino parte comunque dopo un timeout di 5 secondi
        #
        cespazio = True
        aspettato_troppo = False
        while cespazio and not aspettato_troppo:
            pacco = self.sede.buffer_temporaneo.preleva(timeout=5)
            if pacco is None:
                aspettato_troppo = True
            if not aspettato_troppo and not furgoncino.deposita_pacco(pacco):
                self.sede.buffer_temporaneo.deposita(pacco)
                cespazio = False

    def run(self):
        while True:
            furgoncino = self.sede.garage_arrivi.preleva()
            self.display.log(f"[{self.sede.nome}] Scarico {furgoncino}")
            self._scarica(furgoncino)
            self._carica(furgoncino)
            self.display.log(f"[{self.sede.nome}] Pronto per partenza: {furgoncino}")
            self.sede.garage_partenze.deposita(furgoncino)


# ---------------------------------------------------------------------------
# Guidatore
# ---------------------------------------------------------------------------

class Guidatore(Thread):
    """
    Guida un furgoncino dalla sede corrente alla sede successiva, poi rientra a piedi.
    Ciclo:
      1. Preleva un furgoncino dal Garage_partenze della sede corrente.
      2. Registra la partenza sulla TrattaStradale e viaggia (sleep).
      3. Consegna il furgoncino al Garage_arrivi della sede successiva.
      4. Registra il rientro a piedi sulla TrattaStradale e torna (sleep).
    """
    def __init__(self, tratta, display):
        super().__init__()
        self.tratta = tratta
        self.display = display

    def run(self):
        nome_tratta = f"{self.tratta.sede_da.nome}->{self.tratta.sede_a.nome}"
        while True:
            furgoncino = self.tratta.preleva_e_parte()
            self.display.log(f"[{nome_tratta}] Parto con {furgoncino}")
            time.sleep(random.uniform(0.5, 2.0))
            self.tratta.deposita_e_arriva(furgoncino)
            self.display.log(f"[{nome_tratta}] Arrivato in {self.tratta.sede_a.nome}, rientro...")
            self.tratta.guidatore_parte_a_piedi()
            time.sleep(random.uniform(0.5, 2.0))
            self.tratta.guidatore_arrivato()
            self.display.log(f"[{nome_tratta}] Rientrato in {self.tratta.sede_da.nome}")


# ---------------------------------------------------------------------------
# ProduttorePacchi
# ---------------------------------------------------------------------------

class ProduttorePacchi(Thread):
    """
    Genera periodicamente pacchi con dimensione e destinatario casuali
    e li deposita nel BufferTemporaneo della propria sede.
    """
    def __init__(self, sede, display, dim_min=1, dim_max=5):
        super().__init__()
        self.sede = sede
        self.display = display
        self.dim_min = dim_min
        self.dim_max = dim_max

    def run(self):
        while True:
            dim = random.randint(self.dim_min, self.dim_max)
            dest = random.choice([s for s in SEDI if s != self.sede.nome])
            pacco = Pacco(dim, self.sede.nome, dest)
            self.sede.buffer_temporaneo.deposita(pacco)
            self.display.log(f"[Produttore {self.sede.nome}] Creato {pacco}")
            time.sleep(random.uniform(0.3, 1.5))


# ---------------------------------------------------------------------------
# Display  -  thread che disciplina la stampa della dashboard e dei log
#
# PUOI TRASCURARE DI STUDIARE QUESTA PARTE, NON SARA' OGGETTO DI ESAME.
# DISPLAY SERVE SOLO COME CLASSE DI SERVIZIO
# PER AVERE STAMPE PULITE E UNA DASHBOARD CHE MOSTRA LO STATO DEL SISTEMA IN TEMPO REALE.
#
# EVITA DI USARE PRINT DURANTE L'ESAME E APPOGGIATI AL METODO LOG DI QUESTA CLASSE PER IL DEBUG
# ---------------------------------------------------------------------------

class Display(Thread):
    """
    Ridisegna la dashboard ogni refresh_interval secondi.
    E' l'unico thread che chiama print(): tutti gli altri inviano messaggi
    tramite Display.log(), che li accoda in modo thread-safe.

    La dashboard mostra:
      - Stato grafico di ciascuna sede (garage_arrivi, buffer, garage_partenze).
      - Frecce tra sedi con '#' per ogni furgoncino in viaggio e 'O' per rientri.
      - Gli ultimi _MAX_LOG messaggi di log.
    """
    _MAX_LOG = 10
    _W = 81  # larghezza interna del box (esclusi i due caratteri di bordo)

    def __init__(self, sedi, tratte, refresh_interval=0.5):
        super().__init__()
        self.sedi = sedi
        self.tratte = tratte
        self.refresh_interval = refresh_interval
        self._lock = Lock()
        self._log = []

    def log(self, msg):
        """Accoda un messaggio di log. Thread-safe, non bloccante."""
        with self._lock:
            self._log.append(msg)
            if len(self._log) > self._MAX_LOG:
                self._log.pop(0)

    def _snapshot(self):
        """
        Acquisisce tutti i lock del sistema contemporaneamente, legge lo stato
        intero e li rilascia insieme: la fotografia ottenuta e' coerente, nessun thread
        puo' modificare nulla tra una lettura e l'altra.
        """
        tutti_i_lock = (
            [lock
             for sede in self.sedi.values()
             for lock in (sede.garage_arrivi.lock, sede.buffer_temporaneo.lock, sede.garage_partenze.lock)]
            + [tratta.lock for tratta in self.tratte.values()]
            + [self._lock]
        )

        for lock in tutti_i_lock:
            lock.acquire()
        try:
            stato = {}
            for nome, sede in self.sedi.items():
                elementi_buf = sede.buffer_temporaneo.elementi
                stato[nome] = {
                    'arrivi':    (len(sede.garage_arrivi.elementi),   sede.garage_arrivi.capacita_max),
                    'n_pacchi':  len(elementi_buf),
                    'kg_pacchi': sum(p.dimensione for p in elementi_buf),
                    'partenze':  (len(sede.garage_partenze.elementi), sede.garage_partenze.capacita_max),
                }
            snapshot_tratte = {
                key: {
                    'vans':    list(tratta.furgoncini_in_viaggio),
                    'rientri': tratta.n_guidatori_in_rientro,
                }
                for key, tratta in self.tratte.items()
            }
            log = list(self._log)
        finally:
            for lock in tutti_i_lock:
                lock.release()

        return stato, snapshot_tratte, log

    def _riga(self, testo):
        """Incornicia testo in una riga del box, riempiendo o troncando a _W caratteri."""
        return '|' + testo[:self._W].ljust(self._W) + '|'

    def _riga_tratta(self, da, a, info_tratta):
        """
        Freccia bidirezionale tra due sedi:
          '#' da sinistra = furgoncino in viaggio  (da -> a)
          'O' da destra   = guidatore in rientro   (a  -> da, vuoto)
        Esempio: '  A <--O--#----> B'
        """
        vans    = info_tratta.get('vans', [])
        rientri = info_tratta.get('rientri', 0)
        freccia = ['-'] * 10 + ['>']
        for i in range(min(len(vans), 5)):       # '#' partono da sinistra
            freccia[3 + i] = '#'
        for i in range(min(rientri, 3)):         # 'O' partono da destra
            freccia[9 - i] = 'O'
        if not vans:
            freccia[-1] = '-'
        if rientri:
            freccia[0] = '<'
        etichetta = ('   ' + '  '.join(str(f) for f in vans)) if vans else ''
        return self._riga(f'    {da} {"".join(freccia)} {a}{etichetta}')

    def _render(self, stato, tratte, log):
        W = self._W
        h = '-' * W
        lines = [
            '+' + h + '+',
            self._riga('  RETE FURGONCINI    A --> B --> C --> D --> A'),
            '+' + h + '+',
            self._riga('  LEGENDA:'),
            self._riga('    Sedi:   [###..] #=furgoncino, .=libero   n/cap=occupati/capienza'),
            self._riga('    Buffer: Np Nkg = N pacchi in transito, peso totale Nkg'),
            self._riga('    Tratte: #=furgoncino in viaggio (-->)   O=guidatore in rientro a piedi (<--)'),
            '+' + h + '+',
        ]

        nomi = list(stato.keys())
        for i, nome in enumerate(nomi):
            s = stato[nome]
            n_g, cap_g = s['arrivi']
            n_p, cap_p = s['partenze']
            barra_g = '#' * n_g + '.' * (cap_g - n_g)
            barra_p = '#' * n_p + '.' * (cap_p - n_p)
            buf_str = f"{s['n_pacchi']:2d}p {s['kg_pacchi']:4d}kg"
            riga = (f"  Sede {nome}  |  Arrivi [{barra_g}] {n_g}/{cap_g}"
                    f"  |  Buffer: {buf_str}"
                    f"  |  Partenze [{barra_p}] {n_p}/{cap_p}")
            lines.append(self._riga(riga))
            nome_succ = nomi[(i + 1) % len(nomi)]
            lines.append(self._riga_tratta(nome, nome_succ, tratte.get((nome, nome_succ), {})))

        lines += [
            '+' + h + '+',
            self._riga('  LOG'),
        ]
        for msg in log:
            lines.append(self._riga('  ' + msg))
        for _ in range(self._MAX_LOG - len(log)):
            lines.append(self._riga(''))
        lines.append('+' + h + '+')

        # Unica chiamata a print: pulisce lo schermo e ridisegna tutto in un colpo
        print('\033[2J\033[H' + '\n'.join(lines), flush=True)

    def run(self):
        while True:
            stato, tratte, log = self._snapshot()
            self._render(stato, tratte, log)
            time.sleep(self.refresh_interval)


# ---------------------------------------------------------------------------
# Setup e avvio
# ---------------------------------------------------------------------------

CAP_ARRIVI        = 3   # posti nel garage_arrivi di ogni sede
CAP_PARTENZE      = 2   # posti nel garage_partenze di ogni sede
CAP_FURGONCINO    = 20  # kg di capienza massima per furgoncino
N_FURGONCINI      = 8   # furgoncini iniziali immessi in sede A
N_LAVORATORI      = 3   # lavoratori per sede
N_GUIDATORI       = 2   # guidatori per tratta

sedi = {nome: Sede(nome, CAP_ARRIVI, CAP_PARTENZE) for nome in SEDI}

tratte = {
    (SEDI[i], SEDI[(i + 1) % len(SEDI)]): TrattaStradale(sedi[SEDI[i]], sedi[SEDI[(i + 1) % len(SEDI)]])
    for i in range(len(SEDI))
}

display = Display(sedi, tratte, refresh_interval=0.5)

for i, nome in enumerate(SEDI):
    sede_corr = sedi[nome]
    tratta = tratte[(nome, SEDI[(i + 1) % len(SEDI)])]
    for _ in range(N_LAVORATORI):
        Lavoratore(sede_corr, display).start()
    for _ in range(N_GUIDATORI):
        Guidatore(tratta, display).start()
    ProduttorePacchi(sede_corr, display).start()

display.start()

# I furgoncini iniziali entrano tutti dalla prima sede
for _ in range(N_FURGONCINI):
    sedi[SEDI[0]].garage_arrivi.deposita(Furgoncino(CAP_FURGONCINO))
