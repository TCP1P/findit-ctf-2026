simple chall

garble-d go binary stelaer -> minidump

my way?
just use bulk extractor, got 2 AES keys, reference it to the minidump raw data -> found POST request /upload and /checksum -> take it out

take a look at aes strings, will found aes.gcm, and by checking those references we know that the structure is
`[key][might be ct+tag+nonce, or smth, just brute the order]`