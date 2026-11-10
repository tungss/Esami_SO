from threading import Thread, Lock, Condition
from os import system
import random
import time

# Dimensione della griglia
dimensione_griglia = 25  

dX = { "nord" : 0, "sud" : 0, "est" : 1, "ovest" : -1 }
dY = { "nord" : -1, "sud" : 1, "est" : 0, "ovest" : 0 }

debug = False

''' 
    Il codice seguente è un simulatore di gioco in cui i giocatori si muovono in una griglia quadrata di dimensione dimensione_griglia.
    A intervalli regolari, i giocatori, rappresentati a video da una "G" maiuscola, si muovono in una delle quattro direzioni possibili.
    Un thread visualizzatore stampa periodicamente lo stato attuale della griglia e gestisce la stampa di messaggi di debug.
'''


'''
    Le istanze di questa classe rappresentano i dati di uno specifico giocatore all'interno di una partita denominata 'game'
    Il metodo muovi consente di spostare il giocatore in una direzione specificata all'interno della griglia di game.
    Il metodo muovi restituisce True se il giocatore è ancora vivo, False altrimenti
'''
class PlayerData:

    def __init__(self,id,game):
        self.id = id
        self.game = game
        self.lock = Lock()
        self.x = random.randint(0, game.dim - 1)
        self.y = random.randint(0, game.dim - 1)
        self.vivo = True

    def muovi(self,direzione):
        with self.lock:
            nuovo_x = self.x + dX[direzione]
            nuovo_y = self.y + dY[direzione]
            if 0 <= nuovo_x < self.game.dim and 0 <= nuovo_y < self.game.dim:
                self.x = nuovo_x
                self.y = nuovo_y
                self.game.dprint(f"Giocatore {self.id} si è mosso in posizione ({self.x}, {self.y})")
            return self.vivo

'''
    Il giocatore è un thread che, ad intervalli regolari, si muove in una direzione casuale all'interno della griglia di game. 
    Ogni thread Giocatore ha un id univoco ed è associato a una istanza di PlayerData gemella
'''
class Giocatore(Thread):
    def __init__(self, id, game):
        super().__init__()  
        self.id = id
        self.game = game

    def run(self):
        while self.compie_azione():
            time.sleep(2)
    
    def compie_azione(self):
        direzione = random.choice(list(dX.keys()))
        return self.game.muovi(self.id, direzione)
    

'''
    La classe GridGame rappresenta una partita in cui nplayers giocatori si muovono all'interno di una griglia quadrata di dimensione dim.
    Questa classe può essere estesa per includere funzionalità aggiuntive e implementare regole di gioco specifiche, 
    come quelle di un gioco di ruolo ispirato alla serie di libri "Twilight".
'''
class GridGame:

    maxStampe = 5
    def __init__(self,dim,nplayers):
        self.dim = dim
        self.codaStampeLock = Lock()
        self.codaStampe = []
        self.nplayers = nplayers
        self.datiGiocatori = [PlayerData(i,self) for i in range(nplayers)]
        self.threadGiocatori = [Giocatore(i,self) for i in range(nplayers)]
        for t in self.threadGiocatori:
            t.start()
        self.stampaMappa = StampaMappa(self)
        self.stampaMappa.start()
    
    #
    # Metodo per muovere uno specifico giocatore in una direzione specificata
    #
    def muovi(self, player, direzione):
        return self.datiGiocatori[player].muovi(direzione)

    #
    # Metodo per prendere il lock su tutti i PlayerData e poter stampare la mappa senza race condition 
    #
    def lockAllPlayers(self):
        for player in self.datiGiocatori:
            player.lock.acquire()

    #
    # Metodo per rilasciare il lock su tutti i PlayerData 
    #
    def unlockAllPlayers(self):
        for player in self.datiGiocatori:
            player.lock.release()

    #
    #  Metodo per inviare messaggi di debug che vengono stampati dal thread visualizzatore nell'ordine in cui arrivano
    #  Da notare che le stampe più vecchie vengono via via rimosse quando la coda delle stampe supera il valore massimo impostato
    #
    def dprint(self,string):
        with self.codaStampeLock:
            self.codaStampe.append(string)
            if len(self.codaStampe) > self.maxStampe:
                self.codaStampe.pop(0)  
    
    def printCodaStampe(self):
        with self.codaStampeLock:
            for p in self.codaStampe:
                print(p)

#
# Thread per la stampa periodica della mappa
#
class StampaMappa(Thread):

    def __init__(self,game):
        super().__init__()
        self.game = game
        self.griglia = [[None for _ in range(game.dim)] for _ in range(game.dim)]

    def run(self):
        iterazioni = 0
        while True:
            #
            # Ripulisco lo schermo, in maniera tale da stampare la griglia sempre nello stesso punto
            #
            system('clear')
            self.game.lockAllPlayers()
            #
            # Prima di ogni stampa la griglia viene riempita con i dati letti dai PlayerData
            #
            for p in self.game.datiGiocatori:
                self.griglia[p.x][p.y] = p.id
            for riga in self.griglia:
                print(''.join(['.' if cella is None else 'G' for cella in riga]))
            #
            # Azzero la griglia per la prossima stampa
            #
            self.griglia = [[None for _ in range(self.game.dim)] for _ in range(self.game.dim)]
            self.game.unlockAllPlayers()
            iterazioni += 1
            print (f"ITER: {iterazioni}")
            self.game.printCodaStampe()
            time.sleep(1)


if __name__ == "__main__":
    #
    # Crea una partita su una griglia di lato 25 con 10 giocatori
    #
    the_game = GridGame(dimensione_griglia,10)
 