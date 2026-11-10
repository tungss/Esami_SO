
from queue import Queue
from threading import Thread,RLock,Condition, current_thread
import random
from time import sleep

#
# Funzione di stampa sincronizzata, utile per il debug
#
plock = RLock()
debug = True
def dprint(s):
    if debug:
        plock.acquire()
        print(s)
        plock.release()

#
#
#  Codice fornito come materiale preliminare, composto dalla classe DatoCondiviso e dalla classe blocking_queue
#
#
    #
    # Le due classi DatoCondiviso e DatoCondivisoSenzaStarvation sono state modificate per consentire la rientranza
    # In particolare sono state aggiunte e gestite le variabili self.currentWriter e self.numLockScrittura.
    # Rimane come piccolo difetto il fatto che un lettore che ha già acquisito il lock in lettura non può prendere il lock in scrittura anche se è l'unico lettore.
    # Questo non crea problemi in questa prova di esame, ma potrebbe in generale dare fastidio in altri contesti.
    #
        
class DatoCondiviso():

    def __init__(self,v):
        self.dato = v
        self.numLettori = 0
        self.numLockScrittura = 0
        self.currentWriter = None
        self.lock = RLock()
        self.condition = Condition(self.lock)

    def getDato(self):
        return self.dato
    
    def setDato(self, i):
        self.dato = i


    def acquireReadLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} prova a prendere il lock in lettura")
        while self.numLockScrittura>0 and self.currentWriter != current_thread():
            dprint(f"Il thread {current_thread().name} voleva leggere ma trova che c'è lo scrittore {self.currentWriter}. Dunque aspetta.")
            self.condition.wait()
        self.numLettori += 1
        dprint(f"Il thread {current_thread().name} prende il lock in lettura")
        self.lock.release()

    def releaseReadLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} rilascia il lock in lettura")
        self.numLettori -= 1
        if self.numLettori == 0:
            self.condition.notify()
        self.lock.release()

    def acquireWriteLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} prova a prendere il lock in scrittura")

        while self.numLettori > 0 or self.numLockScrittura > 0 and self.currentWriter != current_thread():
            dprint(f"Il thread {current_thread().name} voleva scrivere su {self}, ma trova che ci sono {self.numLettori} lettori e che currentWrite={self.currentWriter}. Dunque aspetta.")
            self.condition.wait()
        self.numLockScrittura += 1
        self.currentWriter = current_thread()
        dprint(f"Il thread {current_thread().name} acquisisce il lock in scrittura")
        self.lock.release()

    def releaseWriteLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} rilascia il lock in scrittura")
        self.numLockScrittura -= 1
        if self.numLockScrittura == 0:
            self.currentWriter = None
        self.condition.notify_all()
        self.lock.release()


class DatoCondivisoSenzaStarvation(DatoCondiviso):
    SOGLIAGIRI = 5

    def __init__(self,v):
        super().__init__(v)
        self.numScrittoriInAttesa = 0
        self.numGiriSenzaScrittori = 0

    def acquireReadLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} prova a prendere il lock in lettura")

        #
        # Consento a un thread che ha già il lock in scrittura di bypassare il controllo starvation e prendere il lock in lettura.
        #
        while self.currentWriter != current_thread() and ( 
               self.numLockScrittura > 0 or (self.numScrittoriInAttesa > 0 and self.numGiriSenzaScrittori > self.SOGLIAGIRI) 
            ):
            dprint(f"Il thread {current_thread().name} voleva leggere {self}. Trova che {self.numScrittoriInAttesa} scrittori sono in attesa; \
                    Sono passati {self.numGiriSenzaScrittori} giri senza scrittori. Attualmente c'è lo scrittore: {self.currentWriter}")
            self.condition.wait()
        self.numLettori += 1
        # 
        # 		 * Il contatore viene incrementato solo se effettivamente ci sono
        # 		 * scrittori in attesa.
        # 		 
        if self.numScrittoriInAttesa > 0:
            self.numGiriSenzaScrittori += 1
        dprint(f"Il thread {current_thread().name} prende il lock in lettura")
        self.lock.release()

    def releaseReadLock(self):
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} rilascia il lock in lettura")
        self.numLettori -= 1
        # 
        # 	Nella versione senza starvation, possono esserci anche dei lettori in attesa. 
        #   E' necessario
        #   dunque svegliare tutti.
        # 			 
        if self.numLettori == 0:
            self.condition.notify_all()
        self.lock.release()

    def acquireWriteLock(self):   # No starvation version
        self.lock.acquire()
        dprint(f"Il thread {current_thread().name} prova a prendere il lock in scrittura")
 
        self.numScrittoriInAttesa += 1
        while self.numLettori > 0 or self.numLockScrittura>0 and self.currentWriter != current_thread():
            dprint(f"Il thread {current_thread().name} voleva scrivere su {self}, ma trova che ci sono {self.numLettori} lettori e che currentWrite={self.currentWriter}. Dunque aspetta.")
            self.condition.wait()
        self.ceUnoScrittore += 1
        self.currentWriter = current_thread()
        self.numScrittoriInAttesa -= 1
        self.numGiriSenzaScrittori = 0
        dprint(f"Il thread {current_thread().name} prova a prendere il lock in scrittura")
        self.lock.release()

# Resta uguale a DatoCondiviso
#     def releaseWriteLock(self):
#         lock.acquire()
#         ...
#         lock.release()


class BlockingQueue:

    def __init__(self,dim):
        self.lock = Lock()
        self.full_condition = Condition(self.lock)
        self.empty_condition = Condition(self.lock)
        self.ins = 0
        self.out = 0
        self.slotPieni = 0
        self.dim = dim
        self.thebuffer = [None] * dim
        
    def put(self,c):
        self.lock.acquire()
        
        while self.slotPieni == len(self.thebuffer):
            self.full_condition.wait()
        
        self.thebuffer[self.ins] = c
        self.ins = (self.ins + 1) % len(self.thebuffer)
        
        self.empty_condition.notifyAll()
        
        self.slotPieni += 1
        self.lock.release()

    def show(self):
        
        self.lock.acquire()
        val = [None] * self.dim;
        
        for i in range(0,self.slotPieni):
            val[(self.out + i) % len(self.thebuffer)] = '*'
        
        for i in range(0,len(self.thebuffer) - self.slotPieni):
            val[(self.ins + i) % len(self.thebuffer)] = '-'
        
        print("In: %d Out: %d C: %d" % (self.ins,self.out,self.slotPieni))
        print("".join(val))
        self.lock.release()


    def get(self): 

        self.lock.acquire()
        try:
            while self.slotPieni == 0:
                self.empty_condition.wait()
    
            returnValue = self.thebuffer[self.out]
            self.out = (self.out + 1) % len(self.thebuffer)
            
            self.full_condition.notifyAll()
            
            self.slotPieni -= 1
            return returnValue
        finally:
            self.lock.release()
   
#
#
#   Fine codice fornito come materiale preliminare
#  
#      
import operator

class InteriCombinati:
    def __init__(self):
        self.V = [DatoCondiviso(0) for _ in range(10)] # Inizializza l'array di interi
        #
        # Sfrutto la comoda libreria operator per evitare di scrivere un sacco di if. 
        # In particolare, operator.add è la funzione che somma due numeri, operator.sub sottrae, etc.
        # invocare operator.add(a, b) è del tutto equivalente a scrivere a + b, anche come performance.
        #
        # Non era richiesto, ma è un modo interessante di risolvere il problema.
        #
        self.operazioni = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv, '%': operator.mod}  

    def calcola(self, i, j, op):
       
        #
        # Acquisisco i lock in ordine crescente, in modo da evitare deadlock.
        # Anche se si tratta di operazioni di sola lettura, immagina il caso in cui un thread invoca calcola(1, 2, '+')
        # mentre un altro thread invoca quasi contemporaneamente V[2].acquireWriteLock() e poi V[1].acquireWriteLock().
        #
        for indice in sorted([i, j]):
            self.V[indice].acquireReadLock()    
        
        try:     
            if op in ['/','%'] and self.V[j].getDato() == 0:
                dprint(f"Divisione per zero: non eseguo l'operazione {op} su V[{i}]={self.V[i].getDato()} e V[{j}]={self.V[j].getDato()}")
                raise ZeroDivisionError()
            else:
                return self.operazioni[op](self.V[i].getDato(), self.V[j].getDato())
       
        finally:
            self.V[i].releaseReadLock()
            self.V[j].releaseReadLock()
 
    def aggiorna(self, i, j, k, op):
       
        indici_ordinati = sorted([i, j, k])
        #
        # Qui, la presenza di un write lock mi obbliga ad acquisire i lock in ordine crescente, immagina il caso in cui
        # invoco aggiorna(1, 2, 3, '+') e un altro thread invoca aggiorna(3, 2, 1, '+') contemporaneamente.
        #
        for indice in indici_ordinati:
            if indice == k:
                self.V[indice].acquireWriteLock()
            else:
                self.V[indice].acquireReadLock()
        try:    
            self.V[k].setDato( self.calcola(i,j,op) )
        except ZeroDivisionError:
            dprint(f"Thread {current_thread()}: salto una operazione di divisione per zero")
        finally:
            for indice in indici_ordinati:
                if indice == k:
                    self.V[indice].releaseWriteLock()
                else:
                    self.V[indice].releaseReadLock()

class Calcolatrice:
    def __init__(self):
        self.IC = InteriCombinati()
        self.B = Queue(10)
        self.elaboratori = [Thread(target=self.elabora) for _ in range(4)]
        self.produttori = [Thread(target=self.produce) for _ in range(2)]

        for thread in self.elaboratori + self.produttori:
            thread.start()

    def elabora(self):
        while True:
            i, j, k, op = self.B.get()
            self.IC.aggiorna(i, j, k, op)

    def produce(self):
        ops = ['+', '-', '*', '/', '%']
        while True:
            i, j, k = random.randint(0, 9), random.randint(0, 9), random.randint(0, 9)
            op = random.choice(ops)
            self.B.put((i, j, k, op))

# Esempio di uso
calcolatrice = Calcolatrice()
