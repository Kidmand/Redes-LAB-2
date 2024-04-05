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
        self.socket = socket
        self.directory = directory
        self.connected = True

        local_address = self.socket.getsockname()
        sys.stdout.write('Conected by: %s \n' % str(local_address))

    def handle(self):
        """
        Atiende eventos de la conexión hasta que termina.
        """
        try:
            while self.connected:
                comands_text = self._receive_command()
                if not self.connected:
                    break
                comands = self._analyze_comand(comands_text)
                if not self.connected:
                    break
                self._run_comand(comands)
        finally:
            sys.stdout.write(
                'Closing connection...\n')
            self.socket.close()

    def _receive_command(self):
        buffer = ''

        while EOL not in buffer and self.connected:
            try:
                buffer += self.socket.recv(TAM_COMAND).decode("ascii")
            except UnicodeError:
                self._create_message_and_send(BAD_REQUEST)
                self.connected = False

        if EOL not in buffer:
            self.connected = False
            return []
        else:
            # Dividimos por si tenemos varios comandos.
            buffer_split = buffer.split(EOL)
            if buffer_split[-1] == '':
                buffer_split.pop()

            return buffer_split

    def _analyze_comand(self, commands_text):

        # FIXME: MEJORAR EL FORMATO, ESTA IMPRIMIENDO LA LISTA.
        sys.stdout.write(f'Request: {commands_text}\n')

        comands = []
        for comand in commands_text:
            if EOL in comand or '\n' in comand:
                self._create_message_and_send(BAD_EOL)
                self.connected = False
                break
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
        Redirecciona al metodo que se encarga de satisfacer el comando con sus argumentos.
        """
        message = self._create_message(CODE_OK)
        for (comand, arg) in comands:
            if comand == "get_slice":
                if len(arg) == 3:
                    (res_code, res_message) = self._get_slice(*arg)
                    if (res_code == CODE_OK):
                        message += res_message
                    else:
                        message = self._create_message(res_code)
                        break
                else:
                    message = self._create_message(INVALID_ARGUMENTS)
                    break
            elif comand == "get_metadata":
                if len(arg) == 1:
                    (res_code, res_message) = self._get_metadata(*arg)
                    if (res_code == CODE_OK):
                        message += res_message
                    else:
                        message = self._create_message(res_code)
                        break
                else:
                    message = self._create_message(INVALID_ARGUMENTS)
                    break
            elif comand == "get_file_listing":
                if len(arg) == 0:
                    (res_code, res_message) = self._get_file_listing()
                    message += res_message
                else:
                    message = self._create_message(INVALID_ARGUMENTS)
                    break
            elif comand == "quit":
                if len(arg) == 0:
                    self._quit()
                    break  # Si hacemos quit no seguimos ejecutando comandos.
                else:
                    message = self._create_message(INVALID_ARGUMENTS)
                    break
            else:
                message = self._create_message(INVALID_COMMAND)
                break

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
        files_in_directory = os.listdir(self.directory)

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
        file_path = os.path.join(self.directory, filename)

        if os.path.isfile(file_path):
            file_size = str(os.path.getsize(file_path))
            return (CODE_OK, file_size + EOL)
        else:
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
        file_path = os.path.join(self.directory, str(filename))

        try:
            offset = int(offset)
            size = int(size)
        except ValueError:
            return (INVALID_ARGUMENTS, "")

        if not os.path.isfile(file_path):
            return (FILE_NOT_FOUND, "")

        file_size = os.path.getsize(file_path)
        if offset < 0 or size < 0:
            return (INVALID_ARGUMENTS, "")
        elif offset + size > file_size:
            return (BAD_OFFSET, "")
        else:
            with open(file_path, 'rb') as file:
                file.seek(offset)
                slice = file.read(size)

            encoded_slice = b64encode(slice).decode('ascii')
            message = encoded_slice + EOL
            return (CODE_OK, message)

    def _quit(self):
        """
        Termina la conexión.
        """
        self.connected = False

    def _create_message(self, code):
        return '{} {} {}'.format(code, error_messages[code], EOL)

    def _send_message(self, message):
        self.socket.sendall(message.encode("ascii"))

    def _create_message_and_send(self, code):
        message = self._create_message(code)
        self._send_message(message)


"""
python3 server.py -p 19500
telnet 0.0.0.0 19500
"""
