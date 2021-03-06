#!/usr/bin/env python3
import sqlite3
import zlib
import re
import os
import json


def extractNoteBody(data):
    # Decompress
    try:
        data = zlib.decompress(data, 16+zlib.MAX_WBITS).split(b'\x1a\x10', 1)[0]
    except zlib.error as e:
        return 'Encrypted note'
    # Find magic hex and remove it 
    # Source: https://github.com/threeplanetssoftware/apple_cloud_notes_parser
    index = data.index(b'\x08\x00\x10\x00\x1a')
    index = data.index(b'\x12', index) # starting from index found previously
    # Read from the next byte after magic index
    data = data[index+1:]
    # Convert from bytes object to string
    text = data.decode('utf-8', errors='ignore')
    # Remove title
    lines = text.split('\n')
    if len(lines) > 1:
        return '\n'.join(lines[1:])
    else:
        return ''


def fixStringEnds(text):
    """
    Shortening the note body for a one-line preview can chop two-byte unicode
    characters in half. This method fixes that.
    """
    # This method can chop off the last character of a short note, so add a dummy
    text = text + '.'
    # Source: https://stackoverflow.com/a/30487177
    pos = len(text) - 1
    while pos > -1 and ord(text[pos]) & 0xC0 == 0x80:
        # Character at pos is a continuation byte (bit 7 set, bit 6 not)
        pos -= 1
    return text[:pos]


def readDatabase():
    # Open notes database
    home = os.path.expanduser('~')
    db = home + '/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite'
    conn = sqlite3.connect(db)
    c = conn.cursor()

    # Get uuid string required in full id
    c.execute('SELECT z_uuid FROM z_metadata')
    uuid = str(c.fetchone()[0])

    # Get tuples of note title, folder code, modification date, & id#
    c.execute("""SELECT t1.ztitle1,t1.zfolder,t1.zmodificationdate1,
                        t1.z_pk,t1.znotedata,t2.zdata,t2.z_pk
                 FROM ziccloudsyncingobject AS t1
                 INNER JOIN zicnotedata AS t2
                 ON t1.znotedata = t2.z_pk
                 WHERE t1.ztitle1 IS NOT NULL AND 
                       t1.zmarkedfordeletion IS NOT 1""")
    # Get data and check for d[5] because a New Note with no body can trip us up
    dbItems = [d for d in c.fetchall() if d[5]]

    # Get ordered lists of folder codes and folder names
    c.execute("""SELECT z_pk,ztitle2 FROM ziccloudsyncingobject
                 WHERE ztitle2 IS NOT NULL AND 
                       zmarkedfordeletion IS NOT 1""")
    folderCodes, folderNames = zip(*c.fetchall())

    conn.close()
    return uuid, dbItems, folderCodes, folderNames


def getNotes(searchBodies=False):
    # Custom icons to look for in folder names
    icons = ['📓', '📕', '📗', '📘', '📙']

    # Read Notes database and get contents
    uuid, dbItems, folderCodes, folderNames = readDatabase()
    
    # Sort matches by title or modification date (read Alfred environment variable)
    sortId = 2 if os.getenv('sortByDate') == '1' else 0
    sortInReverse = (sortId == 2)
    dbItems = sorted(dbItems, key=lambda d: d[sortId], reverse=sortInReverse)

    # Alfred results: title = note title, arg = id to pass on, subtitle = folder name, 
    # match = note contents from gzipped database entries after stripping footers.
    items = [{} for d in dbItems]
    for i, d in enumerate(dbItems):
        folderName = folderNames[folderCodes.index(d[1])]
        if folderName == 'Recently Deleted':
            continue
        title = d[0]
        body = extractNoteBody(d[5])
        # Replace any number of \ns with a single space for note body preview
        bodyPreview = ' '.join(body[:100].replace('\n', ' ').split())
        subtitle = folderName + ' | ' + bodyPreview
        if searchBodies:
            match = u'{} {} {}'.format(folderName, title, body)
        else:
            match = u'{} {}'.format(folderName, title)
        # Custom icons for folder names that start with corresponding emoji
        if any(x in folderName[:2] for x in icons):
            iconText = folderName[:2]#.encode('raw_unicode_escape')
            icon = {'type': 'image', 'path': 'icons/' + folderName[0] + '.png'}
            subtitle = subtitle[2:]
        else:
            icon = {'type': 'default'}
        subtitle = fixStringEnds(subtitle)
        items[i] = {'title': title,
                    'subtitle': subtitle,
                    'arg': 'x-coredata://' + uuid + '/ICNote/p' + str(d[3]),
                    'match': match,
                    'icon': icon}

    return json.dumps({'items': items}, ensure_ascii=True)


if __name__ == '__main__':
    print(getNotes(searchBodies=False))
