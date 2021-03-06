#!/usr/bin/env python3
import json
from get_notes import readDatabase


uuid, dbItems, folderCodes, folderNames = readDatabase()

items = []
for i, name in enumerate(folderNames):
    if name != 'New Folder':
        items.append({'title': name,
                      'subtitle': 'Folder',
                      'arg':'x-coredata://' + uuid + '/ICFolder/p' + str(folderCodes[i])})

print(json.dumps({'items': items}))
