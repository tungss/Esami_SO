import threading
import queue
import time
import random

# Liste di code per ingredienti (codici da 0 a 4)
code_ingredienti = [queue.Queue() for _ in range(5)]

#
# code_ingredienti[0] => Coda Lattuga
# code_ingredienti[1] => Coda Bacon
# code_ingredienti[2] => Coda Hamburger
# code_ingredienti[3] => Coda Formaggio
# code_ingredienti[4] => Coda Pomodoro
#
simboli = {
            0: "@@@@",  # Lattuga
            1: "====",  # Bacon
            2: "####",  # Hamburger
            3: "----",  # Formaggio
            4: "oooo"   # Pomodoro
}
nomi = {
            0: "Lattuga",    # Lattuga
            1: "Bacon",      # Bacon
            2: "Hamburger",  # Hamburger
            3: "Formaggio",  # Formaggio
            4: "Pomodoro"    # Pomodoro
}

# 
# Coda per gli ordini
#
coda_ordini = queue.Queue()

#
# Thread produttore di ingredienti
#
class ProduttoreIngredienti(threading.Thread):
    def __init__(self, codice_ingrediente):
        super().__init__()
        self.codice_ingrediente = codice_ingrediente

    def run(self):
        while True:
            # Produce l'ingrediente e lo mette nella coda specifica
            ingrediente = f"Ingrediente {self.codice_ingrediente}"
            code_ingredienti[self.codice_ingrediente].put(ingrediente)
            print(f"Prodotto {nomi[self.codice_ingrediente]}")
            # Simula il tempo di produzione
            time.sleep(random.uniform(0.5, 1.5))

#
# Thread assemblatore di ordini
#
class Assemblatore(threading.Thread):
    def __init__(self):
        super().__init__()

    def run(self):
        while True:
            # Prende un ordine dalla coda degli ordini
            ordine_id, ordine = coda_ordini.get()
            if ordine is None:
                break  # Fine degli ordini

            assemblato = []
            print(f"Assemblaggio ordine {ordine_id}: {ordine}")
            # Preleva gli ingredienti richiesti dall'ordine
            for codice_ingrediente in ordine:
                ingrediente_preso = code_ingredienti[codice_ingrediente].get()
                assemblato.append(ingrediente_preso)
                print(f"Prelevato {ingrediente_preso} per l'ordine {ordine_id}")
                self.stampa_assemblaggio(codice_ingrediente)
            
            print(f"Ordine {ordine_id} completato: {assemblato}")

    def stampa_assemblaggio(self, codice_ingrediente):
       print(simboli[codice_ingrediente])

# Thread che genera gli ordini
class InviatoreOrdini(threading.Thread):
    def __init__(self, ordine_id, ordini):
        super().__init__()
        self.ordine_id = ordine_id
        self.ordini = ordini

    def run(self):
        for ordine in self.ordini:
            print(f"Thread {self.ordine_id} ha inviato ordine: {ordine}")
            coda_ordini.put((self.ordine_id, ordine))
            time.sleep(2)  # Tempo tra gli ordini

# Avvio dei thread produttori per ciascun ingrediente
thread_ingredienti = []
for codice in range(5):
    thread = ProduttoreIngredienti(codice)
    thread.start()
    thread_ingredienti.append(thread)

# Avvio dei thread assemblatori
pasquale_lassemblatore = Assemblatore()
pasquale_lassemblatore.start()

ciccio_lassemblatore = Assemblatore()
ciccio_lassemblatore.start()

liste_ordini = [
    [[0, 1, 2], [2, 3, 4]],                     # liste_ordini[0] => Ordini per il thread 1
    [[0, 4, 1, 3], [1, 2, 0]],                  # liste_ordini[1] => Ordini per il thread 2
    [[4,4,2,1], [0,0,1], [3,3,2]],              # liste_ordini[2] => Ordini per il thread 3
    [[0,0,1], [1,2,3,4], [4,0,4], [3,4,3,4,1]]  # liste_ordini[3] => Ordini per il thread 4
]

#
# Creo e avvio i thread che ordinano
# 
threads_ordini = []
i = 0
for ordini in liste_ordini:
    thread = InviatoreOrdini(i, ordini)
    thread.start()
    threads_ordini.append(thread)
    i += 1
