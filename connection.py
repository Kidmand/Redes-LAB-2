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
                comand_text = self._receive_command()

                for c_text in comand_text:
                    if self.connected:
                        comand = self._analyze_comand(c_text)
                        if comand[0] != '':
                            self._run_comand(comand[0], comand[1])

        finally:
            sys.stdout.write(
                'Closing connection...\n')
            self.socket.close()

    def _receive_command(self):
        buffer = ''

        # FIXME: CREO QUE TODOS LOS ERRORES SUGUEN DE ESTE WHILE.
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

    def _analyze_comand(self, command_text):

        sys.stdout.write(f'Request: {command_text}\n')

        if EOL in command_text or '\n' in command_text:
            self._create_message_and_send(BAD_EOL)
            self.connected = False
            return ('', [])

        command_split = command_text.split()
        if len(command_split) == 0:
            self._create_message_and_send(INVALID_COMMAND)
            return ('', [])
        else:
            comand = command_split[0]
            arg = command_split[1:]

            return (comand, arg)

    def _run_comand(self, comand, arg):
        """
        Redirecciona al metodo que se encarga de satisfacer el comando con sus argumentos.
        """
        match comand:
            case "get_slice":
                if len(arg) == 3:
                    self._get_slice(*arg)
                    return
            case "get_metadata":
                if len(arg) == 1:
                    self._get_metadata(*arg)
                    return
            case "get_file_listing":
                if len(arg) == 0:
                    self._get_file_listing()
                    return
            case "quit":
                if len(arg) == 0:
                    self._quit()
                    return
            case _:
                self._create_message_and_send(INVALID_COMMAND)
                return

        # Esto se ejecuta solo si el match entra a algun caso y no entra al if.
        self._create_message_and_send(INVALID_ARGUMENTS)

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
        message = self._create_message(CODE_OK)

        for file in files_in_directory:
            message += file + EOL

        message += EOL
        self._send_message(message)

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
            message = self._create_message(CODE_OK)
            message += file_size + EOL
            self._send_message(message)
        else:
            message = self._create_message_and_send(FILE_NOT_FOUND)

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
            self._create_message_and_send(INVALID_ARGUMENTS)
            return

        file_size = os.path.getsize(file_path)
        if offset < 0 or size < 0:
            message = self._create_message_and_send(INVALID_ARGUMENTS)
        elif offset + size > file_size:
            message = self._create_message_and_send(BAD_OFFSET)
        elif os.path.isfile(file_path):

            with open(file_path, 'rb') as file:
                file.seek(offset)
                slice = file.read(size)

            encoded_slice = b64encode(slice).decode('ascii')
            message = self._create_message(CODE_OK)
            message += encoded_slice + EOL
            self._send_message(message)
        else:
            message = self._create_message_and_send(FILE_NOT_FOUND)

    def _quit(self):
        """
        Termina la conexión.
        El servidor responde con un resultado exitoso (0 OK) y cierra la conexion.
        """
        self._create_message_and_send(CODE_OK)
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
