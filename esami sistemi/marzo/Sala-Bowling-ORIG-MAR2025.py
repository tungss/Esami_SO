#!/usr/bin/python3

from threading import RLock, Condition, Thread
from time import sleep
from random import randint

'''
MATERIALE PER LA PROVA SULLA PROGRAMMAZIONE MULTI-THREADED 

Il codice fornito implementa un piccolo sistema di gestione di una sala bowling. Una sala da bowling contiene un certo numero di piste P 
e un certo numero N di palle da bowling. Per poter giocare, una squadra composta da M giocatori necessita di avere a disposizione una pista 
e una palla da bowling per ciascun giocatore (dunque devono essere disponibili M palle da bowling).
Ogni pista può essere assegnata a una certa squadra, ammesso che sia disponibile un numero di palle da bowling pari al numero di giocatori per la data squadra. 
Ad esempio, se le palle a disposizione sono 10, e in un certo momento una squadra di 6 giocatori occupa la pista n.1, 
una eventuale squadra di 5 giocatori non potrà usufruire della pista n.2, pur essendo questa libera, poiché le restanti 4 palle non sono sufficienti. 

La classe Sala contiene questi metodi:

richiedi_pista(self, id_squadra, num_giocatori: int, modalita_gentile=False) -> int

Il primo metodo consente di richiedere una pista e una dotazione di palle da bowling specificando un certo numero di giocatori. 
Se la quantità di palle richiesta non è disponibile, oppure non ci sono piste libere, la squadra viene messa in attesa. Viene restituito il codice della pista che è stata assegnata.
Per come funziona il metodo quando modalita_gentile è True, leggi la descrizione del metodo richiedi_pista_gentilmente.

libera_pista(self, num_pista: int, num_giocatori: int) 

Il secondo metodo prevede la liberazione di una pista precedentemente occupata e la restituzione delle palle da bowling non più utilizzate. 

richiedi_pista_gentilmente(self, id_squadra, num_giocatori)

Questo metodo invoca richiedi_pista con la modalita_gentile impostata a True.
Questo metodo si mette in attesa finché non sono disponibili 'num_giocatori' palle da bowling e una pista, proprio come il
metodo richiedi_pista standard. Tuttavia, quando si è in modalità gentile interviene un meccanismo diverso di gestione
della turnazione tra squadre.
Più in dettaglio, quando arriva il turno per una squadra S, ma contemporaneamente non è subito disponibile il
numero di palle da bowling richiesto per la squadra S, allora il thread chiamante si rimette subito in stato di wait, ma retrocedendo di quattro
posti nella lista di attesa. Qualora i thread in attesa subito dopo S siano meno di 4, allora S si metterà in coda.

A corredo trovi anche il codice di una classe Squadra che simula il comportamento casuale di una squadra attraverso un thread. 
La soluzione fornita elimina i potenziali problemi di starvation accodando le richieste delle squadre secondo l'ordine di arrivo.
'''

class Sala:
    
    def __init__(self, num_piste, num_palle):
        self.lock = RLock()
        self.condition = Condition(self.lock)
        self.num_piste = num_piste
        self.piste = [False] * num_piste
        self.palle_disponibili = num_palle
        
        self.prossimo_id = 1
        self.lista_attesa = []

    def richiedi_pista(self, id_squadra, num_giocatori, modalita_gentile=False):
        with self.lock:
            self.lista_attesa.append(id_squadra)
            
            # Per uscire da questo while devono verificarsi tre condizioni:
            # 1) Deve esserci una pista libera
            # 2) Deve esserci un numero sufficiente di palle per la squadra
            # 3) Deve essere il turno della squadra, ossia id_squadra deve essere il primo elemento della lista_attesa
            while (pista:=self._cerca_pista() == -1 or 
                   self.palle_disponibili < num_giocatori or 
                   id_squadra != self.lista_attesa[0]):

                #
                # Sono in blocco per via delle poche palle disponibili e sono in modalità gentile, quindi...
                #     
                if modalita_gentile and id_squadra == self.lista_attesa[0] and pista!=-1:
                    self.lista_attesa.pop(0)
                    #
                    # Siccome mi sto levando dalla cima della lista di attesa, do la possibilità alla prossima squadra di giocare 
                    #
                    self.condition.notify_all()
                    print(f"La squadra {id_squadra} con {num_giocatori} giocatori rimanda il suo turno")
                    if len(self.lista_attesa) >= 4:
                        self.lista_attesa.insert(3, id_squadra)
                    else:
                        self.lista_attesa.append(id_squadra)
                print(f"La squadra {id_squadra} con {num_giocatori} giocatori deve attendere il suo turno")
                self.condition.wait()
                
            self.lista_attesa.pop(0)
            # Essendosi modificata la lista di attesa, notifico per dare la possibilità alla prossima squadra di provare a giocare
            self.condition.notify_all()
            self.palle_disponibili -= num_giocatori
            pista = self._cerca_pista()
            self.piste[pista] = True
            print(f"La squadra {id_squadra} ottiene la pista {pista} con {num_giocatori} giocatori")
            return pista

    def richiedi_pista_gentilmente(self, id_squadra, num_giocatori):
        return self.richiedi_pista(id_squadra, num_giocatori, True)

    def libera_pista(self, num_pista, num_giocatori):
        with self.lock:
            self.palle_disponibili += num_giocatori
            self.piste[num_pista] = False
            # Si sono liberate delle risorse, notifico per dare la possibilità di usare le risorse liberate a chi è in attesa
            self.condition.notify_all()

    # Metodo privato usato per individuare la prima pista libera
    def _cerca_pista(self):
        for i in range(len(self.piste)):
            if not self.piste[i]:
                return i
        return -1


class Squadra(Thread):

    def __init__(self, id_squadra, sala):
        super(Squadra, self).__init__()
        self.sala = sala
        self.id_squadra = id_squadra

    def run(self):
        while True:
            # La squadra fa altro prima di chiedere una pista
            sleep(randint(0,6))
            # Prova a chiedere una pista
            num_giocatori = randint(2,15)
            print(f"La squadra {self.id_squadra} chiede una pista per {num_giocatori} giocatori.")
            pista = self.sala.richiedi_pista_gentilmente(self.id_squadra, num_giocatori)
            print(f"La squadra {self.id_squadra} gioca sulla pista {pista}.")
            # Simula il tempo di gioco
            sleep(randint(1,4))
            self.sala.libera_pista(pista, num_giocatori)
            print(f"La squadra {self.id_squadra} lascia la pista {pista}.")

if __name__ == '__main__':
    # Crea una sala con 4 piste e 20 palle
    sala = Sala(4, 40)
    for i in range(10):
        Squadra(i, sala).start()