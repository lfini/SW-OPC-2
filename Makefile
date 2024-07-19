VERSION = $(shell python opc/utils.py)

PKG = opc_soft-$(VERSION).zip

upd:
	cp -r dome ~/WinShare/opc_soft/
	cp -r focus ~/WinShare/opc_soft/
	cp -r gui ~/WinShare/opc_soft/
	cp -r homer ~/WinShare/opc_soft/
	cp -r opc ~/WinShare/opc_soft/
	cp  setup.cmd ~/WinShare/opc_soft/

kit:
	zip -r $(PKG) dome focus gui homer opc -x\*/__\*__/\* -x\*/.\* -x\*/\*.log -x\*/\*.bck -x\*/\*.json
	zip -r $(PKG) astap/db astap/astap_cli.exe
	zip $(PKG) setup.cmd README

