from threading import Thread, Lock, Barrier
from random import randint, seed
from time import sleep

NUM_GIOCATORI_PER_SQUADRA = 5

class TiroAllaFune:
    
    def __init__(self, soglia=10):
        self.posizione = 0
        self.soglia = soglia
        self.lock = Lock()
        self.vincitore = None

    def start(self):
        self.squadra1 = [Player(self, 1) for _ in range(NUM_GIOCATORI_PER_SQUADRA)]
        self.squadra2 = [Player(self, -1) for _ in range(NUM_GIOCATORI_PER_SQUADRA)]

        for p in self.squadra1 + self.squadra2:
            p.start()

        for p in self.squadra1 + self.squadra2:
            p.join()

        print(f"Vincitore: {self.vincitore}!")


    def tira(self, direzione):
        with self.lock:
            if self.vincitore is None:  # Controlla se il gioco è ancora attivo
                self.posizione += direzione
                self.stampa_situazione()

                if self.posizione >= self.soglia:
                    self.vincitore = "Squadra 1"
                elif self.posizione <= -self.soglia:
                    self.vincitore = "Squadra 2"

            return self.vincitore is None  # True se il gioco continua, False se è finito

    def stampa_situazione(self):
        # Pulisce schermo
        print("\033[H\033[J")
        # Stampa graficamente la posizione della fune
        print("=" * (self.soglia + self.posizione) + "|" + "=" * (self.soglia - self.posizione))

class Player(Thread):

    def __init__(self, game: TiroAllaFune, direzione: int):
        super().__init__()
        self.game = game
        self.direzione = direzione

    def run(self):
        
        while True:
            sleep(randint(1, 3) * 0.5)  # Simula forza diversa tra giocatori
            if not self.game.tira(self.direzione):
                break  # Se il gioco è finito, il thread si ferma

if __name__ == "__main__":
    gioco = TiroAllaFune()
    gioco.start()

