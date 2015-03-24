import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import tornado.gen
import os.path
import uuid

import time

from tornado.options import define, options

define('port', default=8005, help='run on the given port', type=int)

class Application(tornado.web.Application):
    def __init__(self):

        handlers = [
            (r"/", MainHandler),
            (r"/jobs", ListHandler),
            (r"/ws", WebsockHandler)
        ]
        settings = dict(
            cookie_secret="__SOMETHING_GOES_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):

        body = self.get_argument('command', '')


        if len(body):
            cmd = tornado.escape.to_basestring(body)
            message = 'adding new job to queue: %s' % cmd
            WebsockHandler.new_work({'cmd': cmd, 'start_time': 'asap'})
        else:
            message = 'yay you successfully found this page.  type \'?command=echo hello\' to submit a new RPC'

        self.render('index.html', message=message)

class ListHandler(tornado.web.RequestHandler):
    def get(self):

        self.render('list.html', jobs=list(WebsockHandler.jobs.values()), workers=list(WebsockHandler.workers))

class WebsockHandler(tornado.websocket.WebSocketHandler):

    workers = []
    jobs = {}
    min_workers = 4
    next_worker = 0

    def check_origin(self, origin):
        return True

    def get_compression_options(self):
        return {}

    def open(self):
        self.id = str(uuid.uuid4())[:6]

        WebsockHandler.workers.append(self)

        WebsockHandler._update()

    def on_close(self):
        WebsockHandler.workers.remove(self)

    @staticmethod
    @tornado.gen.coroutine
    def _update():

        while True:
            if len(WebsockHandler.workers) > 0:
                for v in WebsockHandler.jobs.values():
                    if len(v['assigned_to']) > 0:
                        for w in WebsockHandler.workers:
                            if str(w.id) == str(v['assigned_to']):
                                #w.write_message(r'{"cmd":"need_update", "body":""}')
                                break

            yield tornado.gen.sleep(1)

    @classmethod
    def new_work(cls, job):

        posting = {'id': str(str(uuid.uuid4())[:6]),
                   'target_job': str(str(uuid.uuid4())[:6]),
                   'assigned_to': '',
                   'cmd': 'new',
                   'body': job,
                   'created_on': time.time(),
                   'output': ''
                   }

        cls.jobs[posting['target_job']] = posting

        if len(cls.workers) > 0:
            posting['assigned_to'] = cls.workers[cls.next_worker].id

            cls.workers[cls.next_worker].write_message(tornado.escape.json_encode(posting))

            cls.next_worker = (cls.next_worker + 1) % len(cls.workers)

            cls.jobs[posting['target_job']] = posting


    def on_message(self, message):
        logging.info('got message %r', message)

        parsed = tornado.escape.json_decode(message)

        posting = WebsockHandler.jobs.get(parsed.get('target_job', None), None)

        logging.info("posting: %r", posting)

        if posting is None:
            logging.warning('status update for non-existant job %s', parsed.get('target_job', 0))
        else:
            if parsed['cmd'] == 'update':
                WebsockHandler.jobs[parsed['target_job']]['output'] += parsed['body']
            elif parsed['cmd'] == 'success':
                logging.info('job %s complete: %s', parsed['target_job'], parsed['body'])
                WebsockHandler.jobs[parsed['target_job']]['output'] = parsed['body']
                WebsockHandler.jobs[parsed['target_job']]['cmd'] = 'complete'

            elif parsed['cmd'] == 'failure':
                logging.error('job %s failed: %s', parsed['target_job'], parsed['body'])
                WebsockHandler.jobs[parsed['target_job']] = None

        self.write_message(r'{"cmd":"ack", "body":""}')

def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(8005)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
