# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $

import sys
import socket
import os
from constants import *
from base64 import b64encode

TAM_COMAND = 4096


class Connection(object):
    """
    Conexión punto a punto entre el servidor y un cliente.
    Se encarga de satisfacer los pedidos del cliente hasta
    que termina la conexión.
    """

    def __init__(self, socket, directory):
        # Guardamos el socket y el directorio.
        self.socket = socket
        self.directory = directory
        # Indicamos que la conexión está activa.
        self.connected = True
        # Diccionario que mapea los comandos a sus respectivos métodos.
        self.COMMAND_HANDLERS = {
            "get_file_listing": (0, self._get_file_listing),
            "get_metadata": (1, self._get_metadata),
            "get_slice": (3, self._get_slice),
            "quit": (0, self._quit)
        }

        # Imprimimos la dirección del cliente.
        local_address = self.socket.getsockname()
        sys.stdout.write('Conected by: %s \n' % str(local_address))

    def handle(self):
        """
        Atiende eventos de la conexión hasta que termina la conexión.
        """
        try:
            while self.connected:
                # Recibimos los comandos del cliente.
                comands_text = self._receive_command()
                if not self.connected:
                    break
                # Analizamos los comandos recibidos.
                comands = self._analyze_comand(comands_text)
                if not self.connected:
                    break
                # Ejecutamos los comandos.
                self._run_comand(comands)
        finally:
            sys.stdout.write(
                'Closing connection...\n')
            self.socket.close()

    def _receive_command(self):
        r"""
        Recibe los comandos del cliente.

        Output:
        - Una lista de cadenas de texto que representan los comandos separados por `EOL`.

        Ejemplo:
        - Si el cliente envia `"comando1 arg1 arg2\r\ncomando2 arg1 arg2\r\n"`, el
        output es `["comando1 arg1 arg2", "comando2 arg1 arg2", ...]`.
        """

        buffer = ""

        # Guardamos los comandos en buffer hasta que encontramos un EOL o se corto la conexion.
        while EOL not in buffer and self.connected:
            try:

                data = self.socket.recv(TAM_COMAND).decode("ascii")
                buffer += data

                # Obs: recv() retorna "" si se corta la conexion desde el cliente.
                if data == "":
                    break
            except UnicodeError:
                self._create_message_and_send(BAD_REQUEST)
                self.connected = False

        # Si NO encontramos un EOL en el buffer, cortamos la conexion.
        if EOL not in buffer:
            self.connected = False
            return []
        else:  # Si lo encontramos, dividimos el buffer en comandos.
            buffer_split = buffer.split(EOL)

            if buffer_split[-1] == "":
                # Removemos el ultimo porque simpre hay un EOL al final
                # y split() nos devuelve "" al ultimo.
                buffer_split.pop()

            return buffer_split

    def _analyze_comand(self, commands_text):
        """
        Analiza los comandos recibidos, revisa que sean validos y los separa en `(comand, args)`.

        Input:
        - `commands_text`: Una lista de cadenas de texto que representan los comandos.

        Output:
        - Una lista de tuplas que contienen el comando y sus argumentos.

        Ejemplo:
        - Input: `["comando1 arg1 arg2", "comando2 arg1 arg2"]`
        - Output: `[("comando1", ["arg1", "arg2"]), ("comando2", ["arg1", "arg2"])]`
        """
        # Imprimimos los comandos recibidos separados por " | ".
        sys.stdout.write(f'Request: {" | ".join(commands_text)}\n')

        # Recorremos los comandos.
        comands = []
        for comand in commands_text:
            # Revisamos que el comando sea valido.
            if EOL in comand or '\n' in comand:
                self._create_message_and_send(BAD_EOL)
                self.connected = False
                break

            # Creamos la tupla (comand, args).
            command_split = comand.split()
            if len(command_split) > 0:
                comand = command_split[0]
                arg = command_split[1:]
                comands.append((comand, arg))
            elif len(command_split) == 0:
                comands.append(("", []))

        return comands

    def _run_comand(self, comands):
        """
        Redirecciona al metodo que se encarga de satisfacer el comando y 
        revisa que se pase la cantidad correcta de argumentos.

        Input:
        - `comands`: Una lista de tuplas que contienen el comando y sus argumentos.

        Ejemplo:
        - Input: `[("comando1", ["arg1", "arg2"]), ("comando2", ["arg1", "arg2"]), ...]`
        """
        # Seteamos el mensaje de respuesta con el codigo de respuesta OK.
        message = self._create_message(CODE_OK)

        # Recorrer los comandos
        for (comand, arg) in comands:
            # Verificar si el comando está definido en el diccionario
            if comand in self.COMMAND_HANDLERS:
                (num_args, func) = self.COMMAND_HANDLERS[comand]
                if len(arg) == num_args:
                    # Ejecutamos el comando.
                    (res_code, res_message) = func(*arg)
                    if comand == "quit":
                        # Si hacemos quit no seguimos ejecutando comandos.
                        break
                    elif res_code == CODE_OK:
                        # Agregamos la respuesta al mensaje.
                        message += res_message
                    else:
                        # Si hay un error, seteamos el mensaje con el codigo de error.
                        message = self._create_message(res_code)
                        break
                else:
                    # Si la cantidad de argumentos no es la correcta.
                    message = self._create_message(INVALID_ARGUMENTS)
                    break
            else:
                # Si el comando no está definido.
                message = self._create_message(INVALID_COMMAND)
                break

        # Enviamos la respuesta al cliente.
        self._send_message(message)

    def _get_file_listing(self):
        """
        Busca obtener la lista de archivos que están actualmente disponibles.
        El servidor responde con una secuencia de líneas terminadas en \r\n, cada una con el nombre de uno de los archivos disponible. 
        Una línea sin texto indica el fin de la lista.

        Ejemplo: 
        Comando:   get_file_listing
        Respuesta: 0 OK\r\n
                   archivo1.txt\r\n
                   archivo2.jpg\r\n
                   \r\n
        """
        # Recuperamos los archivos en el directorio en una lista.
        if os.path.exists(self.directory):
            files_in_directory = os.listdir(self.directory)
        else:
            files_in_directory = []

        # Creamos el mensaje de respuesta.
        message = ""
        for file in files_in_directory:
            message += file + EOL
        message += EOL

        return (CODE_OK, message)

    def _get_metadata(self, filename):
        """
        Este comando recibe un argumento FILENAME especificando un nombre de archivo del cual se pretende averiguar el tamaño. 
        El servidor responde con una cadena indicando su valor en bytes.

        Ejemplo: 
        Comando:   get_metadata ejemplo1.txt
        Respuesta: 0 OK\r\n
                   3199\r\n
        """
        # Buscamos el archivo en el directorio.
        file_path = os.path.join(self.directory, filename)

        # Si el archivo existe, devolvemos su tamaño.
        if os.path.isfile(file_path):
            file_size = str(os.path.getsize(file_path))
            return (CODE_OK, file_size + EOL)
        else:  # Sino, devolvemos un error.
            return (FILE_NOT_FOUND, "")

    def _get_slice(self, filename, offset, size):
        """
        Este comando recibe en el argumento FILENAME el nombre de archivo del que se pretende obtener un slice o parte. 
        La parte se especifica con un OFFSET (byte de inicio) y un SIZE (tamaño de la parte esperada, en bytes), ambos no negativos. 
        El servidor responde con el fragmento de archivo pedido codificado en base64 y un \r\n.
        Byte:      0    5    10   15   20   25   30   35   40
           v    v    v    v    v    v    v    v    v  
        Archivo:   !Que calor que hace hoy, pinta una birra!
        Comando:   get_slice ejemplo1.txt 5 20
        Respuesta: 0 OK\r\n
                   Y2Fsb3IgcXVlIGhhY2UgaG95LCA=\r\n2
        """
        # Buscamos el archivo en el directorio.
        file_path = os.path.join(self.directory, str(filename))

        # Verificamos que los argumentos sean enteros.
        try:
            offset = int(offset)
            size = int(size)
        except ValueError:
            return (INVALID_ARGUMENTS, "")

        # Verificamos que el archivo exista.
        if not os.path.isfile(file_path):
            return (FILE_NOT_FOUND, "")

        # Verificamos que el offset y el size sean validos.
        file_size = os.path.getsize(file_path)
        if offset < 0 or size < 0:
            return (INVALID_ARGUMENTS, "")
        elif offset + size > file_size:
            return (BAD_OFFSET, "")
        else:
            # Leemos el archivo desde el offset hasta el size.
            with open(file_path, 'rb') as file:
                file.seek(offset)
                slice = file.read(size)

            # Codificamos el slice en base64.
            encoded_slice = b64encode(slice).decode('ascii')

            message = encoded_slice + EOL
            return (CODE_OK, message)

    def _quit(self):
        """
        Termina la conexión.
        """
        self.connected = False
        return (CODE_OK, "")

    def _create_message(self, code):
        """
        Crea un mensaje con el código de respuesta correspondiente.

        Input:
        - `code`: Un código de respuesta de `error_messages` en `./constants.py`.
        """
        return '{} {} {}'.format(code, error_messages[code], EOL)

    def _send_message(self, message):
        """
        Envía un mensaje al cliente en formato ASCII.
        """
        self.socket.sendall(message.encode("ascii"))

    def _create_message_and_send(self, code):
        r"""
        Crea un mensaje con el código de respuesta correspondiente y lo envía al cliente.

        Input:
        - `code`: Un código de respuesta de `error_messages` en `./constants.py`.

        Ejemplo:
        - Si `code = 0`, el mensaje es "0 OK\r\n" y se envía al cliente.
        """
        message = self._create_message(code)
        self._send_message(message)
