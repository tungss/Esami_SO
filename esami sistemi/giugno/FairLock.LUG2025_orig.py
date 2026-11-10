'''
Il seguente codice implementa una struttura dati thread-safe, detta FairLock. Un FairLock eredita
il proprio comportamento da quello di un normale Lock rientrante, ma garantisce che
l’ordine di acquisizione del lock corrisponda all’ordine temporale in cui ciascun thread ha
invocato l’operazione di acquire. E’ inoltre disponibile: 
1) l’operazione urgentAcquire, che invece dovrebbe consentire di acquisire il FairLock prima possibile, scavalcando
dunque qualsiasi thread sia già in attesa di prendere il lock;  
2) un sistema di gestione della starvation configurabile.
'''

from threading import Thread,Lock,RLock,Condition, current_thread
from time import sleep
from collections import deque
from random import random


debug = True

class FairLock():
    
    def __init__(self):
        #
        # Lock interno per la gestione della struttura dati
        #
        self.lock = RLock()
        #
        # Tiene traccia della prossima condition da notificare
        #
        self.nextThreadCondition = None
        #
        # Tiene traccia del prossimo thread che ha diritto ad acquisire il lock
        #
        self.nextThread = None
        #
        # Pila LIFO di condition di attesa in urgentAcquire
        #
        self.pilaUrgenti = deque()
        #
        # Coda FIFO di condition di attesa in acquire
        #
        self.codaNormali = deque()
        #
        # Gestione starvation
        #
        self.starvationControl = 0
        self.contaConsecutivi = 0
    #
    # Acquisisce il FairLock se questo è libero. Altrimenti si pone in attesa bloccante 
    # finchè non arriva il proprio turno di acquisizione al lock
    #
    def acquire(self):
        with self.lock:
            myCondition = Condition(self.lock)
            reservation = ( current_thread().ident,myCondition)
            self.codaNormali.append(reservation)
            #
            #Se il lock non è libero e il thread in question non è quello che dovrebbe prendere il lock, aspetta
            #
            while self.nextThread is not None and self.nextThread!=current_thread().ident:
                myCondition.wait()
            #
            #Se il thread ha preso il lock perché era libero, va rimossa la sua condition dalla coda e va impostato il nextThread
            #
            if self.nextThread is None:
                self.codaNormali.remove(reservation)
                self.nextThread = current_thread().ident
            
            if debug:
                self.__print__()

    #
    # Acquisisce il FairLock se questo è libero. Altrimenti si pone in attesa bloccante finchè non
    # arriva il proprio turno di acquisizione al lock. Quando il lock si libera, ai thread che sono bloccati 
    # in questo metodo deve
    # essere data priorità nell’acquisizione del lock secondo le regole menzionate sotto.
    #
    def urgentAcquire(self):
        with self.lock:
            myCondition = Condition(self.lock)
            reservation = ( current_thread().ident,myCondition)
            self.pilaUrgenti.append(reservation)
            #
            #Se il lock non è libero e il thread in question non è quello che dovrebbe prendere il lock, aspetta
            #
            while self.nextThread is not None and self.nextThread!=current_thread().ident:
                myCondition.wait()
            #
            #Se il thread ha preso il lock perché era libero, va rimossa la sua condition dalla pila e va impostato il nextThread
            #
            if self.nextThread is None:
                self.pilaUrgenti.remove(reservation)
                self.nextThread = current_thread().ident

            self.contaConsecutivi += 1
            if debug:
                self.__print__()
    #        
    # Rilascia il proprio accesso al FairLock. Se ci sono dei thread in attesa di acquisire il lock,
    # l’accesso deve essere garantito nell’ordine: ai thread che hanno invocato più recentemente
    # una urgentAcquire, dal più recente al meno recente; ai thread che hanno invocato una
    # normale acquire, partendo dal thread che aspetta da più tempo fino al thread che aspetta
    # più di recente.
    #
    def release(self):
        with self.lock:
            self.nextThreadCondition = None
            self.nextThread = None
            starvationControlActive = (
                                       self.starvationControl > 0 and
                                       len(self.codaNormali) > 0 and 
                                       self.contaConsecutivi >= self.starvationControl
                                      )
            #
            # La starvation e l'ordine di risveglio vengono gestiti
            # decidendo quale condition notificare
            #
            if len(self.pilaUrgenti) > 0 and not starvationControlActive:
                next = self.pilaUrgenti.pop()
                self.nextThread = next[0]
                self.nextThreadCondition = next[1]
                self.nextThreadCondition.notify()
            elif len(self.codaNormali) > 0:
                next = self.codaNormali.popleft()
                self.nextThread = next[0]
                self.nextThreadCondition = next[1]
                self.nextThreadCondition.notify()
                self.contaConsecutivi = 0
                
            if debug:
                self.__print__()
    #
    # Dal momento che le urgentAcquire hanno sempre priorità sulle acquire normali,
    # è possibile configurare la gestione della starvation usando questo metodo. In
    # particolare il parametro n indica il numero di urgentAcquire consecutive, tra quelle in
    # attesa, che possono essere smaltite prima di gestire una eventuale acquire in attesa. Se
    # n=0, il lock non effettua alcun controllo della starvation e smaltisce tutte le
    # urgentAcquire prioritariamente.
    #
    def setStarvationControl(self, n : int ):
        with self.lock:
            self.starvationControl = n
 #
 # Stampa la situazione attuale del lock
 #
    def __print__(self):
        with self.lock:
            print ( 
                    ('%d/%d:' + 
                      'o' * len(self.codaNormali) + 
                      '*' * len(self.pilaUrgenti)) % (self.contaConsecutivi,self.starvationControl)
                  )       

    
    
class JohnLocker(Thread):

    def __init__(self,l : Lock):
        super().__init__()
        self.iterazioni = 10
        self.lock = l

    def run(self):
        while(self.iterazioni > 0):
                self.iterazioni -= 1
                if random() < 0.5:
                    self.lock.acquire()
                else:
                    self.lock.urgentAcquire()
                sleep(random()/10)
                self.lock.release()


L = FairLock()
L.setStarvationControl(10)
for i in range(0,100):
    JohnLocker(L).start()

 
                