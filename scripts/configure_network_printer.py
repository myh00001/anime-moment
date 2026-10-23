"""Switch an existing CUPS queue to Ethernet without submitting a new job."""
import argparse
import ipaddress
import socket
import subprocess

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Printer IPv4 address on the connected interface')
    parser.add_argument('--queue', default='S100_Festival')
    parser.add_argument('--protocol', choices=('ipp', 'socket'), default='ipp')
    args = parser.parse_args()
    host = str(ipaddress.IPv4Address(args.host))
    if not args.queue or not all(c.isalnum() or c in '_-' for c in args.queue):
        parser.error('Invalid CUPS queue name')
    subprocess.run(['lpstat', '-p', args.queue], check=True)
    subprocess.run(['ip', 'route', 'get', host], check=True)
    port = 631 if args.protocol == 'ipp' else 9100
    with socket.create_connection((host, port), timeout=5):
        pass
    uri = f'ipp://{host}:631/ipp/print' if args.protocol == 'ipp' else f'socket://{host}:9100'
    command = ['sudo', 'lpadmin', '-p', args.queue, '-v', uri]
    if args.protocol == 'ipp': command += ['-m', 'everywhere']
    subprocess.run(command, check=True)
    subprocess.run(['sudo', 'cupsenable', args.queue], check=True)
    subprocess.run(['sudo', 'cupsaccept', args.queue], check=True)
    print('Ethernet queue enabled. No new job submitted. Confirm A5/plain media defaults before printing.')

if __name__ == '__main__':
    main()
