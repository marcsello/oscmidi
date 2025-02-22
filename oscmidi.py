import argparse
import json

from pythonosc import dispatcher
from pythonosc import osc_server

import rtmidi


class OscMidi(object):
    def __enter__(self):
        return self

    def __init__(self, portindex, learn, infile, outfile):
        self.midiout = rtmidi.MidiOut()
        self.available_ports = self.midiout.get_ports()
        self.mapping = {"/ping": 0}
        self.learn = learn
        self.infile = infile
        self.outfile = outfile
        self.pool = set(range(1, 127))
        try:
            with open(self.infile) as infile:
                self.mapping = json.load(infile)
            print("loaded mappings from file", self.infile)
        except FileNotFoundError:
            print("no mapping file found, starting from scratch.")

        self.pool -= set(self.mapping.values())
        print("/ping gets mapped to [176, 0, 0] by default")
        print(len(self.mapping), " mappings present")
        print("available midi ports:\n", self.available_ports)

        if self.available_ports:
            self.midiout.open_port(0)
            print("selecting port at index", portindex, ":",
                  self.midiout.get_ports()[portindex], )
        else:
            self.midiout.open_virtual_port("TouchMidi")
            print("open virtual device: TouchMidi")

    def send_message(self, address, *args):
        if address not in self.mapping and self.learn:
            try:
                self.mapping[address] = self.pool.pop()
                print("new", end='')
            except KeyError as e:
                print(e.__cause__)
                print(json.dumps(self.mapping, indent=4))
                print("too many midi mappings. 128 is limit")
                return

        if address in self.mapping:
            control_change = [0xB0, self.mapping[address],
                              round(args[0] * 127) if args else 0]
            self.midiout.send_message(control_change)
            print("\t", address, args, " ==> ", control_change)
        else:
            print("no mapping found and \"--no-learn\" set. not sending midi.")

    def __exit__(self, exception_type, exception_value, traceback):
        with open(self.outfile, mode='w', encoding='utf-8') as outfile:
            json.dump(self.mapping, outfile, indent=2)
        del self.midiout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip",
                        default="0.0.0.0",
                        help="The ip to listen on (default=0.0.0.0)")
    parser.add_argument("--port",
                        type=int,
                        default=5005,
                        help="The port to listen on (default=5005)")
    parser.add_argument("--midi",
                        type=int,
                        default=0,
                        help="The MIDI device index (default=0)")
    parser.add_argument("--mapping-file-in",
                        default="mapping.json",
                        help="File to read for the OSC to MIDI mapping (default=mapping.json)")
    parser.add_argument("--mapping-file-out",
                        default="mapping.json",
                        help="File for saving the mapping (default=mapping.json)")
    parser.add_argument("--no-learn",
                        action="store_true",
                        help="Map new OSC paths to MIDI")
    args = parser.parse_args()

    with OscMidi(args.midi, not args.no_learn, args.mapping_file_in, args.mapping_file_out) as oscmidi:
        d = dispatcher.Dispatcher()
        d.set_default_handler(oscmidi.send_message)

        server = osc_server.ThreadingOSCUDPServer((args.ip, args.port), d)
        print("Serving OSC on {}".format(server.server_address))
        server.serve_forever()


if __name__ == "__main__":
    main()
