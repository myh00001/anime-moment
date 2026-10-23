"""Switch an existing CUPS queue to Ethernet without submitting a new job."""
import argparse
import ipaddress
import socket
import subprocess

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Printer IPv4 address on the connected interface')
    parser.add_argument('--queue', default='S100_Festival')
    args = parser.parse_args()
    host = str(ipaddress.IPv4Address(args.host))
    if not args.queue or not all(c.isalnum() or c in '_-' for c in args.queue):
        parser.error('Invalid CUPS queue name')
    subprocess.run(['lpstat', '-p', args.queue], check=True)
    subprocess.run(['ip', 'route', 'get', host], check=True)
    with socket.create_connection((host, 9100), timeout=5):
        pass
    subprocess.run(['sudo', 'lpadmin', '-p', args.queue, '-v', f'socket://{host}:9100'], check=True)
    subprocess.run(['sudo', 'cupsenable', args.queue], check=True)
    subprocess.run(['sudo', 'cupsaccept', args.queue], check=True)
    print('Ethernet queue enabled; existing driver and page defaults preserved. No new job submitted.')

if __name__ == '__main__':
    main()
