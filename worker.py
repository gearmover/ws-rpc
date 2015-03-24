# -*- coding: utf-8 -*-
from ws4py.client.threadedclient import WebSocketClient
import tornado.escape
import logging
import subprocess


class EchoClient(WebSocketClient):
    def opened(self):

        for i in range(0, 200, 25):
            print(i)
            self.send(r'{"cmd":"ping","body":"yo"}')

    def closed(self, code, reason):
        print(("Closed down", code, reason))

    def received_message(self, m):
        print("=> %d %s" % (len(m), str(m)))

        # try:
        cmd = tornado.escape.json_decode(str(m))

        logging.info('got a json object: %r', cmd)

        try:
            args = tornado.escape.json_decode(str(cmd['body']).replace("u'", '"').replace("'", '"'))['cmd'].split(' ')
        except:
            return

        logging.info('broke cmd into %r', args)

        output = ''

        try:
            p = subprocess.Popen(args, stdout=subprocess.PIPE)
            for line in iter(p.stdout.readline, ''):
                self.send(r'{"cmd":"update","target_job":"'+cmd['target_job']+r'","body":'+tornado.escape.json_encode(line)+'}')
                output = output + line
        except:
            pass


        logging.info('exec came back')

        self.send(r'{"cmd":"success","target_job":"'+cmd['target_job']+r'","body":'+tornado.escape.json_encode(output)+'}')
        #
        # except:
        #     pass

        if len(m) == 175:
            self.close(reason='Bye bye')

if __name__ == '__main__':
    try:
        ws = EchoClient('ws://localhost:8005/ws', protocols=['http-only', 'chat'])
        ws.daemon = False
        ws.connect()
    except KeyboardInterrupt:
        ws.close()