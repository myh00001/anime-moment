"""Set HP M452 tray media using its own web form, preserving unrelated fields."""
import argparse
import http.client
import re
import urllib.parse
import xml.etree.ElementTree as ET

def fetch(host, path, data=None):
    # This firmware truncates dynamic pages when sent Connection: close.
    connection = http.client.HTTPConnection(host, timeout=15)
    try:
        headers = {'Connection': 'keep-alive'}
        if data is not None: headers['Content-Type'] = 'application/x-www-form-urlencoded'
        connection.request('POST' if data is not None else 'GET', path, body=data, headers=headers)
        response = connection.getresponse()
        body = response.read()
        if response.status not in (200, 303): raise RuntimeError(f'HP web settings returned {response.status}')
        return body.decode('utf-8')
    finally:
        connection.close()

def form_values(text, action):
    match = re.search(r'<form\b[^>]*action="'+re.escape(action)+r'"[^>]*>(.*?)</form>', text, re.I | re.S)
    if not match: raise RuntimeError('Complete HP configuration form not found')
    text = match[1]; fields = {}
    for tag in re.findall(r'<input\b[^>]*>', text, re.I):
        attrs = {key.lower(): quoted or bare for key, quoted, bare in re.findall(r'([\w-]+)\s*=\s*(?:"([^"]*)"|([^\s>]+))', tag)}
        name, kind = attrs.get('name'), attrs.get('type', '').lower()
        if not name: continue
        if kind in ('hidden', 'text'): fields[name] = attrs.get('value', '')
        elif kind in ('checkbox', 'radio') and re.search(r'\bCHECKED\b', tag, re.I): fields[name] = attrs.get('value', 'on')
    for attrs, body in re.findall(r'<select\b([^>]*)>(.*?)</select>', text, re.I | re.S):
        name = re.search(r'\bname\s*=\s*"?([\w]+)', attrs, re.I)
        options = re.findall(r'<option\b([^>]*)>', body, re.I)
        if not options: raise RuntimeError('Incomplete select options')
        chosen = next((o for o in options if 'selected' in o.lower()), options[0])
        value = re.search(r'\bvalue\s*=\s*(?:"([^"]*)"|([^\s>]+))', chosen, re.I)
        if name and value: fields[name[1]] = value[1] or value[2]
    return fields

def configure(host):
    path = '/hp/device/set_config_ph.html'
    fields = form_values(fetch(host, path), path+'/config')
    required = {'Tray1Size', 'Tray2Size', 'Tray1Type', 'Tray2Type', 'SizePrompt', 'ManualFeed'}
    if not required.issubset(fields): raise RuntimeError('Required media settings missing')
    fields.update(Tray1Size='16', Tray2Size='16', Tray1Type='2', Tray2Type='2', SizePrompt='EWS_OFF', ManualFeed='EWS_OFF', Apply='Apply')
    fetch(host, path+'/config', urllib.parse.urlencode(fields).encode())
    verified = form_values(fetch(host, path), path+'/config')
    for name in required:
        if verified[name] != fields[name]: raise RuntimeError(f'HP setting did not persist: {name}')
    print('MEDIA_SETTINGS', {name: verified[name] for name in sorted(required)}, flush=True)
    path = '/hp/device/set_config_print.html'
    fields = form_values(fetch(host, path), path+'/config')
    fields.update(A5FeedOrientation='Landscape', Orientation='orient_Portrait', Apply='Apply')
    fetch(host, path+'/config', urllib.parse.urlencode(fields).encode())
    verified = form_values(fetch(host, path), path+'/config')
    if verified.get('A5FeedOrientation') != 'Landscape': raise RuntimeError('A5 feed setting did not persist')
    print('A5_FEED', verified['A5FeedOrientation'], flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    configure(parser.parse_args().host)
