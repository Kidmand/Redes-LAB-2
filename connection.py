# encoding: utf-8
# Revisión 2019 (a Python 3 y base64): Pablo Ventura
# Copyright 2014 Carlos Bederián
# $Id: connection.py 455 2011-05-01 00:32:09Z carlos $

import sys
import socket
import os
from constants import *
from base64 import b64encode

TAM_COMAND = 1024


class Connection(object):
    """
    Conexión punto a punto entre el servidor y un cliente.
    Se encarga de satisfacer los pedidos del cliente hasta
    que termina la conexión.
    """

    def __init__(self, socket, directory):
        # NOTE: Inicializar atributos de Connection
        self.socket = socket
        self.directory = directory
        self.connected = True

    def handle(self):
        """
        Atiende eventos de la conexión hasta que termina.
        """
        try:
            local_address = self.socket.getsockname()

            sys.stdout.write('Conected by: %s \n' % str(local_address))

            # Recibe los datos en trozos y atiende los eventos
            while self.connected:
                # FIXME: REVISAR EL TAMAÑO DEL COMANDO.
                data = self.socket.recv(TAM_COMAND)
                sys.stdout.write('recibido "%s" \n' % data)

                if data:
                    self._satisfacer_pedido(data)
                else:
                    sys.stdout.write('No hay mas datos.\n')
                    break
        except ValueError as e:
            mensaje = '{} {} \n'.format(*e.args)
            self.socket.sendall(mensaje.encode())
        finally:
            sys.stdout.write(
                'Closing connection... \n')
            self.socket.close()

    def _satisfacer_pedido(self, data):
        """
        Determina el pedido que contiene el parametro DATA y redirecciona al metodo que se encarga de satisfacerlo.
        """
        pedido = data.replace(b"\r\n", b"").decode()
        pedido = pedido.split()
        if len(pedido) == 0:
            comando = ""
        else:
            comando = pedido[0]
            arg = pedido[1:]

        match comando:
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
                message = self._create_message(INVALID_COMMAND)
                self.socket.sendall(message.encode())
                return

        # Esto se ejecuta solo si el match entra a algun caso y no entra al if.
        message = self._create_message(INVALID_ARGUMENTS)
        self.socket.sendall(message.encode())

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
        self.socket.sendall(message.encode())

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
        else:
            message = self._create_message(FILE_NOT_FOUND)

        self.socket.sendall(message.encode())

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
        offset = int(offset)
        size = int(size)

        file_size = os.path.getsize(file_path)
        if offset < 0 or size < 0:
            message = self._create_message(INVALID_ARGUMENTS)
        elif offset + size > file_size:
            message = self._create_message(BAD_OFFSET)
        elif os.path.isfile(file_path):
            with open(file_path, 'rb') as file:
                file.seek(offset)
                slice = file.read(size)

            encoded_slice = b64encode(slice).decode()
            message = self._create_message(CODE_OK)
            message += encoded_slice + EOL
        else:
            message = self._create_message(FILE_NOT_FOUND)

        self.socket.sendall(message.encode())

    def _quit(self):
        """
        Termina la conexión.
        El servidor responde con un resultado exitoso (0 OK) y cierra la conexion.
        """
        mensaje = self._create_message(CODE_OK)
        self.socket.sendall(mensaje.encode())
        self.connected = False

    def _create_message(self, code):
        return '{} {} {}'.format(code, error_messages[code], EOL)


"""
python3 server.py -p 19500
telnet 0.0.0.0 19500
"""
