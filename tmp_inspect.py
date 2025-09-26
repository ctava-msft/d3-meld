import inspect
from pprint import pprint
import meld.vault as vault

cls = vault.DataStore
pprint({'DataStore_methods': [name for name in dir(cls) if not name.startswith('_')]})
print('init signature:', inspect.signature(cls.__init__))
print('source of load:')
print(inspect.getsource(cls.load))
