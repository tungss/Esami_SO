# Questo programma implementa un semplice gioco multithread chiamato "Numero Basso".
# Ogni thread-giocatore sceglie un numero casuale tra 1 e 10. Vince chi ha scelto
# il numero più basso che non è stato scelto da nessun altro. Un thread "Monitor"
# osserva la partita e stampa in tempo reale l'identificatore dei thread che hanno
# effettuato una giocata. Tutta la sincronizzazione tra i thread è gestita con
# RLock e Condition per coordinare l'avvio, l'esecuzione e la conclusione della partita.
# La partita viene lanciata nel blocco principale, che istanzia la classe "NumeroBasso"
# e chiama il metodo "gioca" specificando il numero di giocatori.

from threading import Thread, RLock, Condition, current_thread
from random import randint

# Classe Player: ogni thread rappresenta un giocatore che punta un numero casuale tra 1 e 10
class Player(Thread):
    def __init__(self, nb):
        super().__init__()
        self.nb = nb  # Riferimento all'oggetto NumeroBasso

    def run(self):
        self.nb.puntaNumero(randint(1, 10))  # Punta un numero casuale quando il thread parte

# Classe Monitor: thread separato che stampa le giocate mano a mano che vengono fatte
class Monitor(Thread):
    def __init__(self, nb):
        super().__init__()
        self.nb = nb  # Riferimento all'oggetto NumeroBasso

    def run(self):
        self.nb.monitoraPartita()  # Monitora l'andamento della partita
        print("Partita terminata")  # Messaggio a fine partita

# Classe principale che gestisce la logica del gioco "Numero Basso"
class NumeroBasso:
    def __init__(self):
        self.giocate = []  # Inizializzato temporaneamente, sarà un dizionario
        self.lock = RLock()  # Lock rientrante per proteggere le sezioni critiche
        self.threadGioca = Condition(self.lock)  # Condition per coordinare le giocate
        self.ultimeGiocate = []  # Lista dei thread che hanno appena giocato
        self.partitaInCorso = False  # Flag per indicare se la partita è attiva
        self.nGiocate = 0  # Contatore delle giocate effettuate
      
        self.endGame = Condition(self.lock)  # Condition per notificare la fine partita ai player
        self.vincitore = None  # ID del thread vincitore

    def gioca(self, N: int) -> int:
        with self.lock:
            self.giocate = {}  # Dizionario: chiave = numero scelto, valore = lista di thread
            self.nGiocate = 0  # Azzeramento giocate
            self.partitaInCorso = True  # Inizio partita

            Monitor(self).start()  # Avvia un unico thread monitor

            for _ in range(0, N):  # Avvia N thread giocatori
                Player(self).start()

            while self.nGiocate < N:  # Attende che tutti i giocatori abbiano giocato
                self.threadGioca.wait()

            self.partitaInCorso = False  # Fine della partita
            self.threadGioca.notify_all()  # Risveglia il monitor, se in attesa

            self.endGame.notify_all()  # Risveglia tutti i giocatori bloccati in attesa

            # Determina il vincitore: primo numero con una sola puntata (più basso)
            for k in sorted(self.giocate):
                if len(self.giocate[k]) == 1:
                    print(f"Il vincitore è il thread {self.giocate[k][0]} che ha puntato il numero {k}")
                    self.vincitore = self.giocate[k][0]
                    return self.vincitore

            print("Non ci sono vincitori")  # Nessun numero è stato puntato da un solo giocatore
            return 0

    def puntaNumero(self, n: int):
        with self.lock:
            self.giocate.setdefault(n, []).append(current_thread().ident)  # Registra la puntata. Il setdefault serve per inizializzare la lista se il numero non è ancora presente come chiave
            self.nGiocate += 1  # Incrementa il conteggio delle giocate
            self.threadGioca.notify_all()  # Notifica che una nuova giocata è avvenuta
            self.ultimeGiocate.append(current_thread().ident)  # Registra l’identificatore del thread

            while self.partitaInCorso:  # Attende la fine della partita
                self.endGame.wait()

            return self.vincitore == current_thread().ident  # Ritorna True se il thread ha vinto

    def monitoraPartita(self):
        with self.lock:
            conta = 0  # Contatore giocate stampate
            while len(self.ultimeGiocate) == 0 and self.partitaInCorso:
                self.threadGioca.wait()  # Aspetta che almeno una giocata venga fatta
                while len(self.ultimeGiocate) > 0:
                    print(f"Ha appena giocato il Thread {self.ultimeGiocate.pop()}")  # Stampa thread
                    conta += 1
                    print(f"N.{conta}. G:{self.nGiocate}")  # Mostra quante giocate sono state fatte
                if not self.partitaInCorso:
                    return  # Esce quando la partita è finita

# Punto di ingresso del programma
if __name__ == '__main__':
    gameManager = NumeroBasso()  # Crea il gestore della partita
    v = gameManager.gioca(10)  # Avvia una partita con 10 giocatori
