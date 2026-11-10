"""
SISTEMA DI SCOMMESSE SPORTIVE MULTITHREAD

Descrizione generale:
--------------------
Sistema di scommesse live su partite di calcio che simula un ambiente realistico con:
- Partite multiple in corso contemporaneamente
- Risultati che cambiano dinamicamente durante le partite
- Quote che si aggiornano in base al risultato corrente
- Giocatori che scommettono simultaneamente
- Gestione della cassa del banco
- Sincronizzazione thread-safe di tutte le operazioni

Il sistema utilizza il threading per simulare:
- L'andamento in tempo reale delle partite
- L'aggiornamento continuo delle quote
- Le azioni simultanee di più giocatori
- La chiusura delle partite

Classi principali:
-----------------

1. Partita_sbagliata_exception(Exception)
   Eccezione sollevata quando si tenta di attendere il finale di una partita sbagliata

2. Scommessa
   Rappresenta una singola scommessa effettuata da un giocatore
   Attributi:
   - importo_scommesso: importo puntato
   - risultato_scommesso: risultato su cui si è scommesso (0=1, 1=X, 2=2)
   - quota: quota accettata al momento della scommessa
   - p: riferimento alla partita su cui si è scommesso

3. Portafoglio
   Gestisce il saldo di un giocatore in modo thread-safe
   Metodi:
   - accredita(importo): aggiunge denaro al portafoglio
   - addebita(importo): toglie denaro solo se disponibile (ritorna True/False)
   - spendi(importo): toglie denaro anche se porta il saldo in negativo
   - saldo(): restituisce il saldo corrente

4. Banco(Portafoglio)
   Estende Portafoglio per gestire la cassa del banco
   Metodi:
   - incassa_puntata(importo): riceve le puntate dei giocatori
   - paga_vincita(importo): paga le vincite se ha fondi sufficienti

5. Partita
   Rappresenta una partita di calcio con risultati e quote dinamici
   Costanti:
   - RIS1 = 0: vittoria squadra 1
   - RISX = 1: pareggio
   - RIS2 = 2: vittoria squadra 2
   
   Metodi:
   - leggi_quote(): restituisce le quote correnti 
   - set_quote(nuove_quote): aggiorna le quote (solo se partita non terminata)
   - get_risultato(): restituisce il risultato corrente
   - set_risultato(nuovo_risultato): aggiorna il risultato (solo se partita non terminata)
   - scommetti(importo, risultato): crea una scommessa (restituisce tupla (Scommessa, msg))
     dove msg e' "ok" se accettata o il motivo del rifiuto se rifiutata
   - attendi_finale(scommessa): blocca il thread fino alla fine della partita, poi calcola vincita
   - termina_partita(): chiude la partita e notifica tutti i thread in attesa

6. Tabellone
   Contenitore thread-safe per l'elenco delle partite
   Metodi:
   - elenco(): restituisce lista di tutte le partite
   - attive(): restituisce solo le partite non ancora terminate

Thread workers:
--------------

7. Giocatore_thread(threading.Thread)
   Simula un giocatore che scommette continuamente sulle partite attive
   Comportamento:
   - Scorre ciclicamente tutte le partite attive
   - Usa una strategia per scegliere il risultato su cui puntare
   - Verifica di avere fondi sufficienti prima di scommettere
   - Attende la fine di ogni partita per scoprire se ha vinto
   - Si ferma quando non ci sono più partite attive
   
   Attributi:
   - stat_scommesse: numero totale di scommesse effettuate
   - vittorie: numero di scommesse vinte

8. Divino_dio_del_calcio(threading.Thread)
   Simula l'andamento dinamico delle partite cambiando i risultati
   Comportamento:
   - Aggiorna periodicamente il risultato corrente delle partite attive
   - Rispetta le transizioni realistiche: da 1 può andare solo in X o rimanere 1,
     da 2 può andare solo in X o rimanere 2, da X può andare ovunque
   - Evita salti impossibili (es: da 1 a 2 direttamente)

9. Banco_quote_thread(threading.Thread)
   Aggiorna continuamente le quote in base al risultato corrente
   Comportamento:
   - Legge il risultato corrente di ogni partita
   - Abbassa le quote per il risultato in vantaggio (favorito)
   - Alza le quote per gli altri risultati (sfavoriti)
   - Stampa lo stato della cassa del banco

10. Finale_partita_thread(threading.Thread)
    Gestisce la chiusura temporizzata di una partita
    Comportamento:
    - Attende per un tempo prestabilito
    - Termina la partita sul risultato corrente 
    - Notifica tutti i giocatori in attesa del risultato

Funzioni di strategia:
---------------------

11. strategia_semplice(partita)
    Strategia di scommessa: sceglie sempre il risultato con la quota più alta
    Parametri:
    - partita: oggetto Partita su cui decidere
    Ritorna: indice del risultato scelto (0, 1, o 2)

Flusso di esecuzione:
--------------------
1. Creazione delle partite con nomi di squadre reali
2. Inizializzazione del tabellone e del banco
3. Avvio dei thread:
   - Divino_dio_del_calcio: simula l'andamento delle partite
   - Banco_quote_thread: aggiorna le quote in tempo reale
   - Finale_partita_thread (uno per partita): chiude le partite dopo un tempo casuale
   - Giocatore_thread (uno per giocatore): i giocatori scommettono continuamente
4. Attesa della terminazione di tutti i thread
5. Stampa del riepilogo finale con statistiche di ogni giocatore
"""


import threading
import time
import random


class Partita_sbagliata_exception(Exception):
    pass


class Scommessa:
    def __init__(self, importo_scommesso, risultato_scommesso, quota, p):
        self.importo_scommesso = importo_scommesso
        self.risultato_scommesso = risultato_scommesso
        self.quota = quota
        self.p = p


class Portafoglio:
    def __init__(self, nome, saldo_iniziale):
        self.nome = nome
        self._saldo = float(saldo_iniziale)
        self._lock = threading.RLock()

    def accredita(self, importo):
        with self._lock:
            self._saldo += float(importo)
            return self._saldo

    def addebita(self, importo):
        # toglie i soldi solo se ce ne sono abbastanza
        with self._lock:
            importo = float(importo)
            if self._saldo >= importo:
                self._saldo -= importo
                return True
            return False

    def spendi(self, importo):
        # toglie i soldi anche se non bastano: il saldo può andare sotto zero
        with self._lock:
            self._saldo -= float(importo)
            return self._saldo

    def saldo(self):
        with self._lock:
            return self._saldo


class Banco(Portafoglio):
    def __init__(self, budget_iniziale):
        super().__init__("BANCO", budget_iniziale)

    def incassa_puntata(self, importo):
        return self.accredita(importo)

    def paga_vincita(self, importo):
        with self._lock:
            if self._saldo >= importo:
                self._saldo -= importo
                return True
            return False  # non ci sono abbastanza soldi per pagare


class Partita:
    RIS1 = 0
    RISX = 1
    RIS2 = 2

    def __init__(self, nome="Partita"):
        self.nome = nome
        self.risultato_corrente = Partita.RISX
        self.quote = [0.0, 0.0, 0.0]
        self.terminata = False
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

    def leggi_quote(self):
        with self._lock:
            return tuple(self.quote)

    def set_quote(self, nuove_quote):
        if len(nuove_quote) != 3:
            raise ValueError("le quote devono avere esattamente 3 valori")
        with self._lock:
            if self.terminata:
                return
            for i in range(3):
                self.quote[i] = float(nuove_quote[i])

    def get_risultato(self):
        with self._lock:
            return self.risultato_corrente

    def set_risultato(self, nuovo_risultato):
        if nuovo_risultato not in (self.RIS1, self.RISX, self.RIS2):
            raise ValueError("risultato non valido")
        with self._lock:
            if self.terminata:
                return
            self.risultato_corrente = nuovo_risultato

    def scommetti(self, importo, risultato):
        if risultato not in (self.RIS1, self.RISX, self.RIS2):
            raise ValueError("risultato non valido")
        with self._lock:
            if self.terminata:
                return (None, "partita già terminata")
            # Il giocatore accetta la quota corrente offerta dal banco
            quota_corrente = self.quote[risultato]
            return (Scommessa(float(importo), risultato, quota_corrente, self), "ok")

    def attendi_finale(self, s):
        if s.p is not self:
            raise Partita_sbagliata_exception()
        with self._lock:
            while not self.terminata:
                self._cond.wait()
            return s.importo_scommesso * s.quota if self.risultato_corrente == s.risultato_scommesso else 0.0

    def termina_partita(self):
        with self._lock:
            self.terminata = True
            self._cond.notify_all()


class Tabellone:
    # Elenco di partite protetto da lock (per evitare pasticci tra thread)
    def __init__(self, partite):
        self._partite = list(partite)
        self._lock = threading.RLock()

    def elenco(self):
        with self._lock:
            return list(self._partite)

    def attive(self):
        with self._lock:
            return [p for p in self._partite if not p.terminata]


# ------------------------
# THREAD SCRITTI COME CLASSI, OGNUNO CON I PROPRI DATI
# ------------------------

class Giocatore_thread(threading.Thread):
    """Gira sul tabellone e prova a scommettere su ogni partita attiva.
    Si ferma se il suo saldo va sotto zero."""

    def __init__(self, nome, tabellone, strategia, importo, wallet, banco, pausa_s=0.3):
        super().__init__(name=f"Giocatore-{nome}")
        self.nome = nome
        self.tabellone = tabellone
        self.strategia = strategia  # funzione(partita) -> risultato
        self.importo = float(importo)
        self.wallet = wallet
        self.banco = banco
        self.pausa_s = pausa_s
        self.vivo = True
        self.stat_scommesse = 0
        self.vittorie = 0

    def run(self):
        while self.vivo:
            attive = self.tabellone.attive()
            if not attive:
                print(f"[{self.nome}] Nessuna partita attiva. Esco.", flush=True)
                break
            for partita in attive:
                if not self.vivo:
                    break
                risultato = self.strategia(partita)
                quote = partita.leggi_quote()
                print(f"[{self.nome}] Tabellone: {partita.nome} quote={quote}", flush=True)

                s, msg = partita.scommetti(self.importo, risultato)
                if s is None:
                    print(f"[{self.nome}] Scommessa rifiutata su {partita.nome}: {msg}", flush=True)
                    continue

                # Controlla se ci sono abbastanza soldi nel portafoglio
                if not self.wallet.addebita(self.importo):
                    print(f"[{self.nome}] Non ha abbastanza soldi per puntare {self.importo:.2f} su {partita.nome} (saldo={self.wallet.saldo():.2f})", flush=True)
                    continue

                self.banco.incassa_puntata(self.importo)
                self.stat_scommesse += 1
                saldo_post = self.wallet.saldo()
                print(f"[{self.nome}] Scommessa su {partita.nome}: risultato={risultato} quota={s.quota} saldo={saldo_post:.2f}", flush=True)

                vincita = partita.attendi_finale(s)
                if vincita > 0:
                    if self.banco.paga_vincita(vincita):
                        self.wallet.accredita(vincita)
                        self.vittorie += 1
                        print(f"[{self.nome}] VINTO su {partita.nome}: +{vincita:.2f} saldo={self.wallet.saldo():.2f}", flush=True)
                    else:
                        print(f"[{self.nome}] La cassa non ha abbastanza soldi per pagare {vincita:.2f}", flush=True)
                else:
                    print(f"[{self.nome}] Perso su {partita.nome}. saldo={self.wallet.saldo():.2f}", flush=True)

                time.sleep(self.pausa_s)
        print(f"[{self.nome}] STOP — scommesse={self.stat_scommesse} vittorie={self.vittorie} saldo_finale={self.wallet.saldo():.2f}", flush=True)


class Divino_dio_del_calcio(threading.Thread):
    """Thread che simula l'andamento delle partite cambiando i risultati correnti"""
    def __init__(self, tabellone, durata_s, intervallo_s=0.3):
        super().__init__(name="DivinoDioDelCalcio", daemon=True)
        self.tabellone = tabellone
        self.durata_s = durata_s
        self.intervallo_s = intervallo_s

    def run(self):
        t0 = time.time()
        while time.time() - t0 < self.durata_s:
            attive = self.tabellone.attive()
            if not attive:
                break
            for p in attive:
                # Cambia il risultato corrente in modo realistico
                # Non si può passare direttamente da 1 a 2 o viceversa
                risultato_attuale = p.get_risultato()
                
                # Determina i possibili cambiamenti in base al risultato attuale
                if risultato_attuale == Partita.RIS1:
                    # Da 1 si può andare in X o rimanere in 1
                    possibili = [Partita.RIS1, Partita.RISX]
                elif risultato_attuale == Partita.RIS2:
                    # Da 2 si può andare in X o rimanere in 2
                    possibili = [Partita.RIS2, Partita.RISX]
                else:  # Partita.RISX (pareggio)
                    # Dal pareggio si può andare ovunque
                    possibili = [Partita.RIS1, Partita.RISX, Partita.RIS2]
                
                nuovo_risultato = random.choice(possibili)
                p.set_risultato(nuovo_risultato)
                risultato_str = ["1", "X", "2"][nuovo_risultato]
                print(f"[DIO DEL CALCIO] {p.nome} → risultato_corrente={risultato_str}", flush=True)
            time.sleep(self.intervallo_s)


class Banco_quote_thread(threading.Thread):
    def __init__(self, tabellone, banco, durata_s, intervallo_s=0.4):
        super().__init__(name="BancoQuote", daemon=True)
        self.tabellone = tabellone
        self.banco = banco
        self.durata_s = durata_s
        self.intervallo_s = intervallo_s

    def run(self):
        t0 = time.time()
        while time.time() - t0 < self.durata_s:
            attive = self.tabellone.attive()
            if not attive:
                break
            for p in attive:
                # Legge il risultato corrente e aggiorna le quote di conseguenza
                risultato_corrente = p.get_risultato()
                
                # Aggiorna le quote in base al risultato corrente
                # Il risultato in vantaggio ha quota più bassa, gli altri più alta
                nuove = [0.0, 0.0, 0.0]
                for i in range(3):
                    if i == risultato_corrente:
                        # Quota più bassa per il favorito (attualmente in vantaggio)
                        nuove[i] = round(1.2 + random.random() * 1.0, 2)
                    else:
                        # Quote più alte per gli sfavoriti
                        nuove[i] = round(2.5 + random.random() * 2.0, 2)
                
                p.set_quote(nuove)
                print(f"[CASSA] {p.nome} quote={nuove} | soldi_cassa={self.banco.saldo():.2f}", flush=True)
            time.sleep(self.intervallo_s)


class Finale_partita_thread(threading.Thread):
    def __init__(self, partita, attesa_s):
        super().__init__(name=f"Finale-{partita.nome}")
        self.partita = partita
        self.attesa_s = attesa_s

    def run(self):
        print(f"[FINALE] {self.partita.nome} terminerà tra {self.attesa_s:.1f}s", flush=True)
        time.sleep(self.attesa_s)
        # Non setta un risultato finale, ma termina la partita sul risultato corrente
        esito_finale = self.partita.get_risultato()
        self.partita.termina_partita()
        risultato_str = ["1", "X", "2"][esito_finale]
        print(f"[FINALE] {self.partita.nome} terminata con risultato finale={risultato_str}", flush=True)


# Regola di esempio: scegli il risultato con quota più alta

def strategia_semplice(partita):
    q = partita.leggi_quote()
    # Qui si può inventare qualunque strategia: scegliamo il risultato con quota più alta
    max_idx = max(range(3), key=lambda i: q[i])
    return max_idx


if __name__ == "__main__":
    random.seed(42)

    # Lista di squadre
    squadre = [
        "Juventus", "Inter", "Milan", "Napoli", "Roma", "Lazio",
        "Atalanta", "Fiorentina", "Bologna", "Torino", "Sampdoria",
        "Genoa", "Udinese", "Cagliari", "Verona", "Sassuolo",
        "Empoli", "Spezia", "Salernitana", "Venezia", "Lecce",
        "Monza", "Cremonese", "Parma", "Como", "Frosinone",
        "Barcelona", "Real Madrid", "Bayern", "PSG", "Liverpool",
        "Man City", "Chelsea", "Arsenal", "Dortmund", "Atletico"
    ]
    
    # Crea tabellone con N partite usando nomi di squadre
    partite = []
    random.shuffle(squadre)
    for i in range(0, min(len(squadre)-1, 34), 2):
        nome_partita = f"{squadre[i]} vs {squadre[i+1]}"
        p = Partita(nome=nome_partita)
        # Tutte le partite iniziano in pareggio
        p.set_risultato(Partita.RISX)
        partite.append(p)
    
    for p in partite:
        # Quote iniziali equilibrate per il pareggio
        p.set_quote([2.5, 2.2, 2.5])

    tabellone = Tabellone(partite)
    banco = Banco(200.0)

    # Finale per ogni partita con tempi random
    finali = []
    for p in partite:
        attesa = random.uniform(2.0, 5.0)
        finali.append(Finale_partita_thread(p, attesa_s=attesa))

    # Thread che simula l'andamento delle partite
    t_dio_calcio = Divino_dio_del_calcio(tabellone, durata_s=6.0, intervallo_s=0.3)
    
    # Updater quote su tutto il tabellone
    t_banco = Banco_quote_thread(tabellone, banco, durata_s=6.0, intervallo_s=0.5)

    # Giocatori con budget e puntate casuali
    nomi_giocatori = ["Alice", "Bob", "Carlo", "Diana", "Elena", "Franco", "Giulia", "Hugo"]
    giocatori = []
    wallets = []
    
    for nome in nomi_giocatori:
        budget = random.uniform(20.0, 100.0)
        importo_puntata = random.uniform(5.0, 15.0)
        pausa = random.uniform(0.15, 0.4)
        
        wallet = Portafoglio(nome, budget)
        wallets.append(wallet)
        
        giocatore = Giocatore_thread(
            nome, 
            tabellone, 
            strategia_semplice, 
            importo=importo_puntata, 
            wallet=wallet, 
            banco=banco, 
            pausa_s=pausa
        )
        giocatori.append(giocatore)
        print(f"[SETUP] {nome}: budget={budget:.2f}, puntata={importo_puntata:.2f}", flush=True)

    # Start
    t_dio_calcio.start()
    t_banco.start()
    for f in finali:
        f.start()
    for g in giocatori:
        g.start()

    # Join
    for f in finali:
        f.join()
    for g in giocatori:
        g.join()

    # Report finale giocatori
    print("\n" + "="*80)
    print("RIEPILOGO FINALE")
    print("="*80)
    for i, g in enumerate(giocatori):
        print(f"[RIEPILOGO] {g.nome}: scommesse={g.stat_scommesse}, vittorie={g.vittorie}, saldo={wallets[i].saldo():.2f}")

    print("="*80)
    saldi_totali = sum(w.saldo() for w in wallets)
    print(f"[MAIN] Saldo CASSA={banco.saldo():.2f} | Saldo totale giocatori={saldi_totali:.2f}", flush=True)
    print("[MAIN] Fine test.", flush=True)
