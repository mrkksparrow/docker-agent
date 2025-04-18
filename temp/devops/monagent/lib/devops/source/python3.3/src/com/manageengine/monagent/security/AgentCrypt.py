#$Id$
from com.manageengine.monagent.security import *
from com.manageengine.monagent import AgentConstants
import traceback
try:
    from Crypto.Cipher import AES
    from base64 import b64encode, b64decode
except Exception as e:
    pass


def AddPadding(data, interrupt, pad, block_size):
    new_data = ''.join([str(data), interrupt])
    new_data_len = len(new_data)
    remaining_len = block_size - new_data_len
    to_pad_len = remaining_len % block_size
    pad_string = pad * to_pad_len
    return ''.join([new_data, pad_string])

def StripPadding(data, interrupt, pad):
    return str(data,'UTF-8').rstrip(pad).rstrip(interrupt)

def encrypt(str_valueToEncrypt):
    cipher_for_encryption = AES.new(SECRET_KEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return str(EncryptWithAES(cipher_for_encryption, str_valueToEncrypt), 'UTF-8')

def decrypt(str_encryptedValue):
    cipher_for_decryption = AES.new(SECRET_KEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return DecryptWithAES(cipher_for_decryption, bytes(str_encryptedValue,'UTF-8'))

def EncryptWithAES(encrypt_cipher, plaintext_data):
    encrypted=None
    try:
        plaintext_padded = AddPadding(plaintext_data, INTERRUPT, PAD, BLOCK_SIZE)
        encrypted = encrypt_cipher.encrypt(plaintext_padded.encode("utf8"))
    except Exception as e:
        traceback.print_exc()        
    return b64encode(encrypted)

def DecryptWithAES(decrypt_cipher, encrypted_data):
    decoded_encrypted_data = b64decode(encrypted_data)
    decrypted_data = decrypt_cipher.decrypt(decoded_encrypted_data)
    return StripPadding(decrypted_data, INTERRUPT, PAD)
    

def encrypt_with_ss_key(str_valueToEncrypt):
    cipher_for_encryption = AES.new(AgentConstants.SSKEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return str(EncryptWithAES(cipher_for_encryption, str_valueToEncrypt), 'UTF-8')

def decrypt_with_ss_key(str_encryptedValue):
    cipher_for_decryption = AES.new(AgentConstants.SSKEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return DecryptWithAES(cipher_for_decryption, bytes(str_encryptedValue,'UTF-8'))

def encrypt_with_proxy_key(str_valueToEncrypt):
    cipher_for_encryption = AES.new(AgentConstants.AGENT_PS_KEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return str(EncryptWithAES(cipher_for_encryption, str_valueToEncrypt), 'UTF-8')

def decrypt_with_proxy_key(str_encryptedValue):
    cipher_for_decryption = AES.new(AgentConstants.AGENT_PS_KEY.encode("utf8"), AES.MODE_CBC, IV.encode("utf8"))
    return DecryptWithAES(cipher_for_decryption, bytes(str_encryptedValue,'UTF-8'))
    