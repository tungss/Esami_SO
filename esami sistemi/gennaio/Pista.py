import random
import time
from threading import *

# Lunghezza pista
K = 100
# Posizione del traguardo
T = 98

# Direzioni

# Sinistra dello schermo
sinistra = 0

# Destra dello schermo
destra = 1

# Alto dello schermo
alto = 2

# Basso dello schermo
basso = 3

spostamenti = [  (-1, 0), (1, 0), (0, -1), (0, 1) ]

def lettera(num_giocatore):
    
    return chr(ord('A') + num_giocatore) if num_giocatore >= 0 else "Nessuno"

# Pista e Visualizzatore
class Pista:
    def __init__(self, numGiocatori):
        self.pista = [[' ' for _ in range(K + 1)] for _ in range(6)]
        self.fillpista(self.pista[0], '#')
        self.fillpista(self.pista[5], '#')
        for i in range(1, 5):
            self.pista[i][T] = '|'
        self.giocatore_di_turno = -1
        self.mosseDisponibili = 0
        self.winner = -1
        self.numGiocatori = numGiocatori
        self.posizioneX = [0] * numGiocatori
        self.posizioneY = [0] * numGiocatori
        self.lock = Lock()
        self.condition_wait_turno = Condition(self.lock)

        # Posizionamento delle "auto"
        for i in range(numGiocatori):
            self.posizioneX[i] = i // 2 
            self.posizioneY[i] = 2 + i % 2
            self.pista[self.posizioneY[i]][self.posizioneX[i]] = lettera(i)

        self.v = Visualizzatore(self)
        self.v.start()
        self.cars = [Automobile(i, self) for i in range(PLAYERS)]
        for car in self.cars:
            car.start()

    def fillpista(self, l, c):
        for i in range(K):
            l[i] = c         

    #
    # Conta quante celle adiacenti libere ci sono 
    # nella direzione dir rispetto alla posizione dell'auto corrente    
    #
    def leggi(self, dir):
        with self.lock:
            if self.giocatore_di_turno < 0:
                return None
            (dx, dy) = spostamenti[dir]
            X = self.posizioneX[self.giocatore_di_turno] + dx
            Y = self.posizioneY[self.giocatore_di_turno] + dy

            dist = 0
            while self.pista[Y][X] == ' ':
                dist += 1
                X += dx
                Y += dy
            return self.pista[Y][X], dist

    def prendi_e_lancia_dado(self, g):
        with self.lock:
            #
            # Si può provare ad accaparrarsi il dado quando questo è libero
            #
            while self.giocatore_di_turno != -1:
                 self.condition_wait_turno.wait()
            self.giocatore_di_turno = g
            self.mosseDisponibili = random.randint(1, 3)
            return self.mosseDisponibili

    def muovi(self, dir):
        with self.lock:
            
            self.mosseDisponibili -= 1

            (dx, dy) = spostamenti[dir]
            X = self.posizioneX[self.giocatore_di_turno]
            Y = self.posizioneY[self.giocatore_di_turno]

            if self.pista[Y + dy][X + dx] != ' ':
                if self.pista[Y + dy][X + dx] == '|':
                    self.winner = self.giocatore_di_turno
                # Non posso muovermi dunque annullo anche le mosse successive
                self.mosseDisponibili = 0
            else:
                self.pista[Y + dy][X + dx] = self.pista[Y][X]
                self.pista[Y][X] = ' '
                self.posizioneX[self.giocatore_di_turno] = X + dx
                self.posizioneY[self.giocatore_di_turno] = Y + dy

            if self.mosseDisponibili == 0:
                self.giocatore_di_turno = -1
                self.condition_wait_turno.notify_all()
                return False
            
            return True

    def get_vincitore(self):
        with self.lock:
            return self.winner

    def visualizza(self):
        with self.lock:
            # pulisce lo schermo
            print("\033[H\033[J")
            for i in range(6):
                print(''.join(self.pista[i]))
            #print(f"E' il turno di : {lettera(self.giocatore_di_turno)}")
            #print(f"Mosse disponibili: {self.mosseDisponibili}")
            if self.winner >= 0:
                print(f"Vincitore = {lettera(self.winner)}")


class Visualizzatore(Thread):
    def __init__(self, p):
        super().__init__()
        self.p = p

    def run(self):
        while self.p.get_vincitore() < 0:
            time.sleep(0.1)  
            self.p.visualizza()
        # Ultima visualizzazione
        self.p.visualizza()


class Automobile(Thread):
    def __init__(self, n, p):
        super().__init__()
        self.nt = n
        self.p = p

    def pensa(self):
        c, dist = self.p.leggi(destra)
        # se posso vado a destra e cioè avanzo verso il traguardo posto a destra
        if c == '|' or dist > 0:
            return destra
        
        # se non posso tento in alto nello schermo
        c, dist = self.p.leggi(alto)
        if dist > 0:
            return alto
        
        # altrimenti tento in basso nello schermo
        c, dist = self.p.leggi(basso)
        if dist > 0:
            return basso
        return -1

    def run(self):
            while self.p.get_vincitore() < 0:
                #print(f"Auto {chr(ord('A') + self.nt)} gioca")
                mosse = self.p.prendi_e_lancia_dado(self.nt) 
                while True:
                    direzione_dove_voglio_andare = self.pensa()
                    if not self.p.muovi(direzione_dove_voglio_andare):
                         break
                time.sleep(1)


# Main
PLAYERS = 26
print("Starting Game...")
p = Pista(PLAYERS)

