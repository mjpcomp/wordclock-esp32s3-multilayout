#!/usr/bin/env python3
"""Apply exactly the reviewed UI polish; validate all inputs/outputs before writes."""
from pathlib import Path
import hashlib

INPUT = {'webpage/style.css': 'b816aa82eebe7410b2114bc84a10283f275500c26f6f8fdc123da94cf553b128', 'webpage/language/en.js': '0238f54c773223b8f8be3a0626182eebf686d6a43e627e439254642d365ea233', 'tests/test_english_ui_cleanup.py': '064a8075a2072672c81584fd570bbe1cc19d7feb1725471ffa5d52e4d1a601ec'}
OUTPUT = {'webpage/style.css': '5cd97ab05f3b9fb3e030ca9be8b63a869082333e250c2a44fdf0b38c057216df', 'webpage/language/en.js': 'c6a4aecd2b7d28d3f390e96b88b5168e46becff849d9ad101509cc3fa440277d', 'tests/test_english_ui_cleanup.py': '5d2cf34853ce1d07e228f836e8268ac7130e49b2564549fb43b8147e5ab6100c'}
OLD_RULE = '.menu .language {\n    margin: 0.6em;\n    border: 1px solid rgb(255 255 255 / 24%);\n    width: calc(100% - 1.2em);\n    min-height: var(--app-control-height);\n    color: #fff;\n    background: rgb(255 255 255 / 12%);\n    box-shadow: inset 0 1px 0 rgb(255 255 255 / 18%);\n}\n'
NEW_RULE = '.menu .language {\n    margin: 0.6em;\n    border: 1px solid rgb(255 255 255 / 24%);\n    width: calc(100% - 1.2em);\n    min-height: var(--app-control-height);\n    color: var(--app-text);\n    background: var(--app-surface-solid);\n    color-scheme: light;\n    box-shadow: inset 0 1px 0 rgb(255 255 255 / 18%);\n}\n\n.menu .language option {\n    color: var(--app-text);\n    background-color: var(--app-surface-solid);\n}\n'
OLD_MODE = '\t\t\t"digital-clock": "Digital Clock",\n\t\t\t"scrollingtext": "Scrolling text",\n\t\t\t"rainbow": "Rainbow",'
NEW_MODE = '\t\t\t"digital-clock": "Digital Clock",\n\t\t\t"scrollingtext": "Scrolling Text",\n\t\t\t"rainbow": "Rainbow",'
CHECKS = 'const css=fs.readFileSync(path.join(root,"webpage/style.css"),"utf8");\nconst languageRule=css.match(/\\.menu \\.language\\s*\\{([^}]+)\\}/)[1];\nconst optionRule=css.match(/\\.menu \\.language option\\s*\\{([^}]+)\\}/)[1];\nassert(languageRule.includes("color: var(--app-text);"));\nassert(languageRule.includes("background: var(--app-surface-solid);"));\nassert(languageRule.includes("color-scheme: light;"));\nassert(optionRule.includes("color: var(--app-text);"));\nassert(optionRule.includes("background-color: var(--app-surface-solid);"));\n'

def once(text,old,new):
 if text.count(old)!=1:raise ValueError('Missing/repeated UI-polish anchor')
 return text.replace(old,new,1)

def main():
 outputs={}
 for name,expected in INPUT.items():
  data=Path(name).read_bytes()
  if hashlib.sha256(data).hexdigest()!=expected:raise SystemExit('Unexpected UI-polish input: '+name)
  text=data.decode('utf-8')
  if name=='webpage/style.css':text=once(text,OLD_RULE,NEW_RULE)
  elif name=='webpage/language/en.js':text=once(text,OLD_MODE,NEW_MODE)
  else:
   text=once(text,'scrollingtext,"Scrolling text"','scrollingtext,"Scrolling Text"')
   text=once(text,'for(const text of [script,ui,english])new vm.Script(text);',CHECKS+'for(const text of [script,ui,english])new vm.Script(text);')
  output=text.encode('utf-8')
  if hashlib.sha256(output).hexdigest()!=OUTPUT[name]:raise SystemExit('Unexpected UI-polish output: '+name)
  outputs[name]=output
 for name,data in outputs.items():Path(name).write_bytes(data)
 print('Applied language-selector contrast, Scrolling Text label and regression assertions.')
if __name__=='__main__':main()
