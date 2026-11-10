import threading
from typing import Dict, List
from enum import Enum
import time
import random


class IscrizioneStatus(Enum):
    """Stato dell'iscrizione"""
    ATTESA = "attesa"
    ACCETTATA = "accettata"
    RIFIUTATA = "rifiutata"


class Figlio:
    """Rappresenta un figlio da iscrivere"""
    
    def __init__(self, id: str, nome: str, genitore_id: str):
        self.id = id
        self.nome = nome
        self.genitore_id = genitore_id
    
    def __repr__(self):
        return f"Figlio({self.id}, {self.nome})"


class Iscrizione:
    """Rappresenta un'iscrizione di un figlio a una scuola"""
    
    def __init__(self, figlio_id: str, scuola_nome: str, status: IscrizioneStatus, timestamp: float):
        self.figlio_id = figlio_id
        self.scuola_nome = scuola_nome
        self.status = status
        self.timestamp = timestamp
    
    def __repr__(self):
        return f"Iscrizione({self.figlio_id}, {self.scuola_nome}, {self.status.value})"


class Scuola:
    """Rappresenta un istituto scolastico con limite di iscrizioni"""
    
    def __init__(self, nome: str, max_iscrizioni: int):
        self.nome = nome
        self.max_iscrizioni = max_iscrizioni
        self._iscritti = []  # Lista di figlio_id
        self._lock = threading.Lock()
    
    def iscrivere(self, figlio_id: str) -> bool:
        """
        Tenta di iscrivere un figlio. 
        Restituisce True se l'iscrizione è stata accettata, False altrimenti.
        """
        with self._lock:
            if len(self._iscritti) < self.max_iscrizioni:
                self._iscritti.append(figlio_id)
                print(f"✓ {figlio_id} iscritto a {self.nome} ({len(self._iscritti)}/{self.max_iscrizioni})")
                return True
            else:
                print(f"✗ {figlio_id} RIFIUTATO da {self.nome} (pieno: {self.max_iscrizioni}/{self.max_iscrizioni})")
                return False
    
    def get_num_iscritti(self) -> int:
        """Restituisce il numero di iscritti attuali"""
        with self._lock:
            return len(self._iscritti)
    
    def get_iscritti(self) -> List[str]:
        """Restituisce una copia della lista degli iscritti"""
        with self._lock:
            return self._iscritti.copy()


class SistemaIscrizioni:
    """Sistema centrale per gestire le iscrizioni con vincoli"""
    
    def __init__(self):
        self.scuole: Dict[str, Scuola] = {}
        self.iscrizioni: Dict[str, Iscrizione] = {}  # figlio_id -> Iscrizione
        self._lock = threading.Lock()
    
    def aggiungi_scuola(self, nome: str, max_iscrizioni: int):
        """Aggiunge una nuova scuola al sistema"""
        with self._lock:
            self.scuole[nome] = Scuola(nome, max_iscrizioni)
    
    def iscrivere_figlio(self, figlio: Figlio, scuola_nome: str) -> bool:
        """
        Iscrive un figlio a una scuola.
        Vincolo: un figlio può essere iscritto a una sola scuola.
        """
        with self._lock:
            # Verifica se il figlio è già iscritto
            if figlio.id in self.iscrizioni:
                print(f"⚠ {figlio.id} è già iscritto a {self.iscrizioni[figlio.id].scuola_nome}")
                return False
            else:
                self.iscrizioni[figlio.id] = Iscrizione(
                    figlio_id=figlio.id,
                    scuola_nome=scuola_nome,
                    status=IscrizioneStatus.ATTESA,
                    timestamp=time.time()
                )
            # Verifica che la scuola esista
            if scuola_nome not in self.scuole:
                print(f"✗ Scuola {scuola_nome} non trovata")
                return False
        
        scuola = self.scuole[scuola_nome]
        iscritto = scuola.iscrivere(figlio.id)
        
        if iscritto:
            with self._lock:
                #Registra l'iscrizione andata a buon fine
                self.iscrizioni[figlio.id].status=IscrizioneStatus.ACCETTATA
            return True
        else:
            del self.iscrizioni[figlio.id]
            return False
    
    def get_statistiche(self) -> str:
        """Restituisce le statistiche delle iscrizioni"""
        with self._lock:
            stats = "📊 STATISTICHE ISCRIZIONI:\n"
            stats += "=" * 50 + "\n"
            for nome_scuola, scuola in self.scuole.items():
                num = scuola.get_num_iscritti()
                stats += f"{nome_scuola}: {num}/{scuola.max_iscrizioni} iscritti\n"
            stats += "=" * 50 + f"\nTotale iscrizioni: {len(self.iscrizioni)}\n"
            return stats


class Genitore(threading.Thread):
    """Thread che rappresenta un genitore che iscrive i figli a scuola"""
    
    def __init__(self, genitore_id: str, figli: List[Figlio], 
                 sistema: SistemaIscrizioni, preferenze_scuole: List[str]):
        super().__init__(name=f"Genitore-{genitore_id}")
        self.genitore_id = genitore_id
        self.figli = figli
        self.sistema = sistema
        self.preferenze_scuole = preferenze_scuole
    
    def run(self):
        """Esegue il processo di iscrizione per ogni figlio"""
        for figlio in self.figli:
            # Scelta casuale della scuola dalle preferenze
            scuola_scelta = random.choice(self.preferenze_scuole)
            
            # Simula un piccolo delay per il processo di iscrizione
            time.sleep(random.uniform(0.01, 0.1))
            
            print(f"👤 {self.name} tenta di iscrivere {figlio.nome} a {scuola_scelta}")
            self.sistema.iscrivere_figlio(figlio, scuola_scelta)


def main():
    """Funzione principale per simulare il sistema di iscrizioni"""
    
    print("🏫 SISTEMA DI ISCRIZIONI SCOLASTICHE MULTITHREAD\n")
    
    # Creazione del sistema
    sistema = SistemaIscrizioni()
    
    # Aggiunta delle scuole
    sistema.aggiungi_scuola("Liceo Scientifico A", max_iscrizioni=3)
    sistema.aggiungi_scuola("Liceo Classico B", max_iscrizioni=3)
    sistema.aggiungi_scuola("Istituto Tecnico C", max_iscrizioni=2)
    sistema.aggiungi_scuola("Istituto Professionale D", max_iscrizioni=2)
    
    print("Scuole disponibili:")
    for nome_scuola, scuola in sistema.scuole.items():
        print(f"  - {nome_scuola} (max {scuola.max_iscrizioni} iscritti)")
    print()
    
    # Creazione dei genitori con i loro figli
    num_genitori = 10
    figli_per_genitore = 2
    
    genitori_dati = []
    figlio_count = 1
    for genitore_id in range(1, num_genitori + 1):
        figli = []
        for _ in range(figli_per_genitore):
            figlio = Figlio(
                id=str(figlio_count),
                nome=f"figlio_{id}",
                genitore_id=str(genitore_id)
            )
            figli.append(figlio)
            figlio_count+=1
        genitori_dati.append((str(genitore_id), figli))
    
    # Creazione e avvio dei thread per ogni genitore
    thread_list = []
    print("Avvio iscrizioni...\n")
    
    for genitore_id, figli in genitori_dati:
        # Preferenze casuali di scuole
        preferenze = random.sample(list(sistema.scuole.keys()), k=random.randint(2, 3))
        
        genitore_thread = Genitore(genitore_id, figli, sistema, preferenze)
        thread_list.append(genitore_thread)
        genitore_thread.start()
    
    # Attesa della fine di tutti i thread
    for thread in thread_list:
        thread.join()
    
    # Stampa delle statistiche finali
    print("\n" + sistema.get_statistiche())
    
    # Dettagli delle iscrizioni
    print("\n📋 DETTAGLI ISCRIZIONI:")
    print("=" * 50)
    for figlio_id, iscrizione in sorted(sistema.iscrizioni.items(), key=lambda x: int(x[0])):
        print(f"{figlio_id}: {iscrizione.scuola_nome} ({iscrizione.status.value})")
    print("=" * 50)


if __name__ == "__main__":
    main()