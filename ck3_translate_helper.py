import sys, argparse, hashlib
from pathlib import Path
from os.path import relpath, basename, exists, dirname
from os import makedirs, remove, rmdir
from collections import OrderedDict

def main():
    args = parse_args()
    args.func(args)

def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='List of commands')

    create_parser = subparsers.add_parser('create', help='Initialize localization by lang')
    create_parser.add_argument('-r', '--root', help="root localization directory", required=True)
    create_parser.add_argument('-sl', '--slang', help="source lang", default="english")
    create_parser.add_argument('-tl', '--tlang', help="target lang", required=True)
    create_parser.set_defaults(func=create_localization)

    update_parser = subparsers.add_parser('update', help='Сollate the target localization with the source')
    update_parser.add_argument('-r', '--root', help="root localization directory", required=True)
    update_parser.add_argument('-sl', '--slang', help="source lang", default="english")
    update_parser.add_argument('-tl', '--tlang', help="target lang", required=True)
    update_parser.add_argument('-c', '--check', help="check only", default=False)
    update_parser.set_defaults(func=update_localization)

    return parser.parse_args()

#region Helpers
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class levels:
    INFO = 'info'
    ERROR = 'error'
    WARNING = 'warning'
    DEBUG = 'debug'

def colored(value, color, color_end):
    return f'{color}{value}{color_end}'

def print_ext(level, template, rel=None, lang=None, idx=None, xkey=None):
    level_color = ''

    if level == levels.INFO:
        level_color = bcolors.OKBLUE
    elif level == levels.ERROR:
        level_color = bcolors.FAIL
    elif level == levels.WARNING:
        level_color = bcolors.WARNING
    elif level == levels.DEBUG:
        level_color = bcolors.OKCYAN

    rel = colored(rel, bcolors.OKGREEN, bcolors.ENDC)
    lang = colored(lang, bcolors.OKGREEN, bcolors.ENDC)
    idx = colored(idx, bcolors.OKGREEN, bcolors.ENDC)
    xkey = colored(xkey, bcolors.OKGREEN, bcolors.ENDC)

    template = template.format(rel=rel, lang=lang, idx=idx, xkey=xkey)

    print(f'{level_color}{level.upper()}:{bcolors.ENDC} {template}')

def load_localization(root, lang):
    directory = Path(root, lang)
    files = list(directory.rglob("*.yml"))

    result = {}
    paths = {}

    for path in files:
        dct = OrderedDict()
        checksum = {}

        rel = relpath(path, directory)

        l_mark = False
        idx = 0
        with open(path, mode='r', encoding='utf-8-sig') as file:
            for line in file:
                line = line.strip()
                idx += 1

                if line.isspace() or not line:
                    continue

                if line.startswith('#!checksum'):
                    xkey, xvalue = line[10:].strip().split('-')

                    checksum[xkey] = xvalue
                    continue

                if line.startswith('#'):
                    continue

                if l_mark == False:
                    l_mark = True
                    if line == f'l_{lang}:':
                        print_ext(levels.DEBUG, 'Parse file {rel} from {lang} localization tag', lang=lang, rel=rel)
                    else:
                        print_ext(levels.ERROR, 'File {rel} has invalid localization tag in line {idx}', rel=rel, idx=idx)
                        return
                    continue

                dpos = line.find(':')

                if dpos == -1:
                    print_ext(levels.ERROR, 'File {rel} has invalid key-value definition in line {idx}', rel=rel, idx=idx)
                    return
                
                
                if len(line) == dpos+1:
                    print_ext(levels.WARNING, 'File {rel} has unset value in line {idx}', rel=rel, idx=idx)
                    continue

                spos = line.find('"')

                if spos == -1 or not line.endswith('"'):
                    print_ext(levels.ERROR, 'File {rel} has invalid key-value definition in line {idx}', rel=rel, idx=idx)
                    return

                key = line[:spos].rstrip()
                value = line[spos:][1:][:-1]

                hash_xkey = hashlib.md5(key.encode('utf-8')).hexdigest()
                dct[hash_xkey] = { 'xkey': key, 'xvalue': value }

        path_hash = hashlib.md5(rel.split(f'{lang}.yml', 1)[0].encode('utf-8')).hexdigest()

        result[path_hash] = { 'data': dct, 'checksum': checksum }
        paths[path_hash] = rel

    return { 'localization': result, 'paths': paths }

def write_localization(root, lang, result):
    for key, rel in result['paths'].items():
        makedirs(Path(root, lang, dirname(rel)), exist_ok=True)

        with open(Path(root, lang, rel), "w", encoding='utf-8-sig') as file:
            file.write("")

            file.write(f'l_{lang}:\n')

            value = result['localization'][key]

            for hash_xkey, o in value['data'].items():
                xvalue = o['xvalue']
                xkey = o['xkey']
                hash_xvalue = value['checksum'][hash_xkey]

                file.write(f'    #!checksum {hash_xkey}-{hash_xvalue}\n')

                if 'xovalue' in o:
                    xovalue = o['xovalue']
                    file.write(f'#    {xkey} "{xovalue}"\n\n')

                file.write(f'    {xkey} "{xvalue}"\n\n')

#endregion

def create_localization(args):
    if exists(Path(args.root, args.tlang)):
        print_ext(levels.ERROR, 'Target localization {lang} already exists', lang=args.tlang)
        return

    if not exists(Path(args.root, args.slang)):
        print_ext(levels.ERROR, 'Source localization {lang} doesn\'t exist', lang=args.slang)
        return

    src = load_localization(args.root, args.slang)
    trg = { 'localization': {}, 'paths': {} }

    for key, value in src['localization'].items():
        path = src['paths'][key]
        rel = path.replace(f'_{args.slang}.yml', f'_{args.tlang}.yml')

        trg['paths'][key] = rel
        trg['localization'][key] = { 'data': {}, 'checksum': {} }
        
        for hash_xkey, o in value['data'].items():
            xvalue = o['xvalue']
            xkey = o['xkey']
            hash_xvalue = hashlib.md5(xvalue.encode('utf-8')).hexdigest()

            trg['localization'][key]['data'][hash_xkey] = { 'xkey': xkey, 'xvalue': xvalue }
            trg['localization'][key]['checksum'][hash_xkey] = hash_xvalue
    
    write_localization(args.root, args.tlang, trg)
    print_ext(levels.INFO, 'Localization {lang} was created from source', lang=args.tlang)
    

def update_localization(args):
    if not exists(Path(args.root, args.tlang)):
        print_ext(levels.ERROR, 'Target localization {lang} doesn\'t exist', lang=args.tlang)
        return

    if not exists(Path(args.root, args.slang)):
        print_ext(levels.ERROR, 'Source localization {lang} doesn\'t exist', lang=args.slang)
        return

    src = load_localization(args.root, args.slang)
    trg = load_localization(args.root, args.tlang)
    trgu = { 'localization': {}, 'paths': {} }

    for key, value in src['localization'].items():
        path = src['paths'][key]
        trg_rel = path.replace(f'_{args.slang}.yml', f'_{args.tlang}.yml')

        if key not in trg['localization']:
            print_ext(levels.WARNING, 'Target localization file {rel} doesn\'t exist', rel=trg_rel)

        trgu['paths'][key] = trg_rel
        trgu['localization'][key] = { 'data': {}, 'checksum': {} }

        for hash_xkey, o in value['data'].items():
            xvalue = o['xvalue']
            xkey = o['xkey']
            hash_xvalue = hashlib.md5(xvalue.encode('utf-8')).hexdigest()

            value_modified = False
            key_missing = False

            if hash_xkey not in trg['localization'][key]['checksum']:
                print_ext(levels.WARNING, 'Key {xkey} in file {rel} doesn\'t exist', rel=trg['paths'][key], xkey=xkey)
                key_missing = True

            if hash_xvalue != trg['localization'][key]['checksum'][hash_xkey]:
                print_ext(levels.ERROR, 'Key {xkey} in file {rel} was modified', rel=trg['paths'][key], xkey=xkey)
                value_modified = True

            trgu['localization'][key]['checksum'][hash_xkey] = hash_xvalue

            if key_missing:
                trgu['localization'][key]['data'][hash_xkey] = { 'xkey': xkey, 'xvalue': xvalue }
            elif value_modified:
                xovalue = trg['localization'][key]['data'][hash_xkey]['xvalue']
                trgu['localization'][key]['data'][hash_xkey] = { 'xkey': xkey, 'xvalue': xvalue, 'xovalue': xovalue }
            else:
                xvalue = trg['localization'][key]['data'][hash_xkey]['xvalue']
                trgu['localization'][key]['data'][hash_xkey] = { 'xkey': xkey, 'xvalue': xvalue }

    for key, value in trg['localization'].items():
        path = trg['paths'][key]

        if key not in src['localization']:
            print_ext(levels.ERROR, 'Target localization file {rel} is superfluous', rel=path)
            remove(Path(args.root, args.tlang, path))
            rmdir(Path(args.root, args.tlang, dir(path)), ignore_errors=True)
            continue

        for hash_xkey, o in value['data'].items():
            xvalue = o['xvalue']
            xkey = o['xkey']

            if hash_xkey not in src['localization'][key]['data']:
                print_ext(levels.ERROR, 'Key {xkey} in file {rel} is superfluous', rel=path, xkey=xkey)
                continue

    write_localization(args.root, args.tlang, trgu)
    print_ext(levels.INFO, 'Localization {lang} was updated from source', lang=args.tlang)
    

if __name__ == "__main__":
    main()
