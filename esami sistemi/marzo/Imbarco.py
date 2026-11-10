from random import randint
from threading import Lock
from threading import Thread
from time import sleep


POSTI_PER_FILA = 6
CORRIDOIO_DOPO = 2  # layout 0 1 2 | 3 4 5


class StopFlag:
	# Flag condiviso di stop tra thread.

	def __init__(self):
		self.stop = False


class Posto:
	# Singolo posto con lock dedicato.

	def __init__(self):
		self.lock = Lock()
		self.occupante = None

	def libero(self):
		with self.lock:
			return self.occupante is None

	def occupa(self, passeggero):
		with self.lock:
			if self.occupante is not None:
				return False
			self.occupante = passeggero
			return True

	def libera(self):
		with self.lock:
			precedente = self.occupante
			self.occupante = None
			return precedente

	def leggi_occupante(self):
		with self.lock:
			return self.occupante


class CabinaCondivisa:
	# Struttura dati condivisa per una cabina con N file e 6 posti per fila.
	# Ogni fila ha layout 3+3 con corridoio tra posto 2 e posto 3.

	def __init__(self, numero_file):
		self.numero_file = numero_file
		# Ogni elemento e un oggetto Posto con lock indipendente.
		self._posti = []
		for _ in range(numero_file):
			fila = []
			for _ in range(POSTI_PER_FILA):
				fila.append(Posto())
			self._posti.append(fila)

	def posto_libero(self, fila, posto):
		return self._posti[fila][posto].libero()

	def occupa(self, fila, posto, passeggero):
		# Occupa un posto se libero. Ritorna True se successo, False altrimenti.
		return self._posti[fila][posto].occupa(passeggero)

	def libera(self, fila, posto):
		# Libera un posto e ritorna il passeggero precedente (o None).
		return self._posti[fila][posto].libera()

	def stampa_cabina(self):
		# Blocca tutti i posti, costruisce la stampa verticale e poi rilascia i lock.
		for i in range(self.numero_file):
			for j in range(POSTI_PER_FILA):
				self._posti[i][j].lock.acquire()

		testo = ""
		for i in range(self.numero_file):
			linea = "F" + str(i) + " "
			for j in range(POSTI_PER_FILA):
				occupante = self._posti[i][j].occupante
				if occupante is None:
					linea += "[ ]"
				else:
					linea += "[O]"

				if j == CORRIDOIO_DOPO:
					linea += " | "

			testo += linea + "\n"

		i = self.numero_file - 1
		while i >= 0:
			j = POSTI_PER_FILA - 1
			while j >= 0:
				self._posti[i][j].lock.release()
				j -= 1
			i -= 1

		print(testo, end="")
		return testo


class PrenotatoreThread(Thread):
	# Prova continuamente a prenotare posti casuali finche non riceve stop.

	def __init__(self, nome, cabina, stop_flag):
		super().__init__()
		self.nome = nome
		self.cabina = cabina
		self.stop_flag = stop_flag
		self.contatore = 0

	def run(self):
		while not self.stop_flag.stop:
			fila = randint(0, self.cabina.numero_file - 1)
			posto = randint(0, POSTI_PER_FILA - 1)
			etichetta = self.nome + "-" + str(self.contatore)
			prenotato = self.cabina.occupa(fila, posto, etichetta)
			if prenotato:
				self.contatore += 1
			sleep(0.2)


class StampatoreThread(Thread):
	# Stampa periodicamente la situazione della cabina in verticale.

	def __init__(self, cabina, stop_flag, intervallo_secondi):
		super().__init__()
		self.cabina = cabina
		self.stop_flag = stop_flag
		self.intervallo_secondi = intervallo_secondi

	def run(self):
		while not self.stop_flag.stop:
			print("\033[2J\033[H", end="")
			self.cabina.stampa_cabina()
			sleep(self.intervallo_secondi)

	

if __name__ == "__main__":
	cabina = CabinaCondivisa(numero_file=8)
	stop_flag = StopFlag()

	prenotatori = []
	for i in range(5):
		nome = "T" + str(i)
		th = PrenotatoreThread(nome, cabina, stop_flag)
		prenotatori.append(th)

	stampatore = StampatoreThread(cabina, stop_flag, 0.8)

	for th in prenotatori:
		th.start()
	stampatore.start()

	sleep(4)
	stop_flag.stop = True

	for th in prenotatori:
		th.join()
	stampatore.join()

	print("Stato finale:")
	cabina.stampa_cabina()
	