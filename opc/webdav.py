"""
Invio file a ICT/INAF via WebDAV

Note:

Account OwnCloud per archivio dati (Attivato 25/3/2021)
    https://owncloud.ia2.inaf.it
    ID: OssChianti
    PW: 2020exo-OPC

Per identificare la URL di accesso via WebDAV, dalla home-page dell'account cliccare
in basso a sinistra: impostazioni
"""
from webdav3.client import Client
from webdav3.exceptions import RemoteResourceNotFound


OWN_CLOUD_PASSCODE = "VHFCB-VZHXT-VLZKU-LKOOF"
OWN_CLOUD_ACTIVITY = "archivia"

OPTIONS = {
        'webdav_hostname': "https://owncloud.ia2.inaf.it/remote.php/dav/files/OssChianti/",
        'webdav_login': "OssChianti",
        'webdav_password': "2020exo-OPC"
        }

class WDav:
    "Operazioni WebDAV per OPC"
    def __init__(self, remote_root):
        self.client = Client(OPTIONS)
        self.remote_root = remote_root

    def make_dir(self, dirname):
        "Crea nuova directory per dati nell'area relativa"
        dirpath = self.remote_root+"/"+dirname
        self.client.mkdir(dirpath)

    def send_file(self, local_file, remote_file):
        "Invia file (asincrono)"
        remote_path = self.remote_root+"/"+remote_file
        self.client.upload_sync(remote_path=remote_path, local_path=local_file)

    def check_dir(self, dirname):
        "Verifica esistenza directory remota"
        remote_path = self.remote_root+"/"+dirname
        try:
            self.client.list(remote_path)
        except RemoteResourceNotFound:
            ret = False
        else:
            ret = True
        return ret

    def check_file(self, filepath):
        "Verifica esistenza directory remota"
        remote_path = self.remote_root+"/"+filepath
        try:
            self.client.info(remote_path)
        except RemoteResourceNotFound:
            return False
        return True

def test():
    "Procedura di test"
    client = Client(OPTIONS)

    info = client.free()
    print("Spazio disponibile:", info)
    info = client.list()
    print("Lista files:", info)

if __name__ == "__main__":
    test()
