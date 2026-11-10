"""
Esempio d'uso del ThreadPool definito in ThreadPool.py: il pool viene usato
per parallelizzare un calcolo vero e proprio, cioe' contare quanti numeri
primi ci sono in un intervallo, spezzando l'intervallo in tanti sotto-
intervalli ed eseguendo un Job per ciascuno.

NOTA: Questo è solo un esempio di utilizzo del threadpool. LA TRACCIA DI ESAME NON SARA' SUI NUMERI PRIMI!


Esegui con:  python3 esempio_uso.py
"""

from time import time
from threading import Lock
from ThreadPool import ThreadPool, Job


def e_primo(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


class ContaPrimiJob(Job):
    """
    Conta quanti numeri primi ci sono nell'intervallo [inizio, fine) e
    memorizza il risultato in una lista condivisa tra tutti i job, protetta
    da un lock dedicato (risultati_lock): NON e' lo stesso lock del pool,
    perche' la lista dei risultati e' uno stato condiviso indipendente dal
    pool, quindi si merita il proprio lock.
    """

    def __init__(self, pool_lock, inizio, fine, risultati, risultati_lock):
        super().__init__(pool_lock)
        self.inizio = inizio
        self.fine = fine
        self.risultati = risultati
        self.risultati_lock = risultati_lock

    def execute(self):
        conteggio = 0
        for n in range(self.inizio, self.fine):
            if e_primo(n):
                conteggio += 1

        with self.risultati_lock:
            self.risultati.append(conteggio)


def sottointervalli(inizio, fine, n_pezzi):
    """Spezza [inizio, fine) in n_pezzi sotto-intervalli quasi uguali."""
    ampiezza = (fine - inizio) // n_pezzi
    limiti = []
    cursore = inizio
    for i in range(n_pezzi):
        prossimo = fine if i == n_pezzi - 1 else cursore + ampiezza
        limiti.append((cursore, prossimo))
        cursore = prossimo
    return limiti


def main():
    N_THREAD = 4
    LIMITE = 200_000
    N_JOB = 8

    pool = ThreadPool(N_THREAD)
    risultati = []
    risultati_lock = Lock()

    jobs = [
        ContaPrimiJob(pool.lock, inizio, fine, risultati, risultati_lock)
        for inizio, fine in sottointervalli(2, LIMITE, N_JOB)
    ]

    inizio_calcolo = time()
    for job in jobs:
        pool.submit(job)

    pool.wait_for_start(jobs[0])
    print(f"il primo job e' partito (pool con {N_THREAD} thread, {N_JOB} job)")

    pool.wait_for_termination()
    durata = time() - inizio_calcolo

    totale = sum(risultati)
    print(f"numeri primi in [2, {LIMITE}): {totale} (calcolati in {durata:.2f}s)")

    # Verifica di correttezza: ricalcolo in sequenziale sullo stesso intervallo.
    atteso = sum(1 for n in range(2, LIMITE) if e_primo(n))
    assert totale == atteso, f"atteso {atteso}, ottenuto {totale}"
    print("risultato verificato contro il calcolo sequenziale\n")

    # --- hurry_and_stop() ---------------------------------------------------
    # Sottomettiamo un ultimo batch di job "pesanti" e chiediamo al pool di
    # terminarli il prima possibile (creando nuovi worker se necessario) e di
    # non accettare piu' submit().
    risultati_finali = []
    ultimo_batch = [
        ContaPrimiJob(pool.lock, inizio, fine, risultati_finali, risultati_lock)
        for inizio, fine in sottointervalli(LIMITE, LIMITE + 100_000, 6)
    ]
    for job in ultimo_batch:
        pool.submit(job)

    print("hurry_and_stop(): forza la fine di tutti i job in coda")
    pool.hurry_and_stop()
    print(f"numeri primi in [{LIMITE}, {LIMITE + 100_000}): {sum(risultati_finali)}")

    try:
        pool.submit(ContaPrimiJob(pool.lock, 0, 1, [], risultati_lock))
    except Exception as e:
        print(f"submit() dopo hurry_and_stop() solleva: {type(e).__name__}")


if __name__ == "__main__":
    main()
