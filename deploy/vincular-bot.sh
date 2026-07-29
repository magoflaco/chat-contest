#!/bin/bash
# Vincula el gateway de Chat Contest a un numero de WhatsApp nuevo.
#
# La sesion anterior se guarda con la fecha en el nombre, nunca se borra. Si el
# escaneo no llega a completarse, se restaura sola y el bot vuelve a quedar
# como estaba: cortar a la mitad no deja el servicio sin cuenta.

set -u

BOT=/home/contest/chat-contest/bot
RESPALDO="auth_info_baileys.$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -ne 0 ]; then
    echo "correlo con sudo." >&2
    exit 1
fi

cd "$BOT" || exit 1

terminar() {
    echo
    # creds.json existe desde el primer segundo, asi que su presencia no dice
    # nada. Lo que aparece recien cuando el telefono confirma es "me", con el
    # JID de la cuenta. Ojo con "registered": suena a lo que buscamos y no lo
    # es, se queda en false hasta en una sesion vinculada y andando.
    if grep -qE '"me":[[:space:]]*\{' "$BOT/auth_info_baileys/creds.json" 2>/dev/null; then
        echo "vinculado. levantando el servicio..."
        echo "la sesion anterior queda en $BOT/$RESPALDO; borrala cuando"
        echo "compruebes que el bot responde."
    else
        echo "la vinculacion no se completo: se restaura la sesion anterior."
        rm -rf "$BOT/auth_info_baileys"
        [ -d "$BOT/$RESPALDO" ] && mv "$BOT/$RESPALDO" "$BOT/auth_info_baileys"
    fi

    chown -R contest:contest "$BOT/auth_info_baileys" 2>/dev/null
    systemctl start chat-contest-bot
    sleep 15
    echo
    journalctl -u chat-contest-bot --since -20s -o cat | grep -E '^\[whatsapp\]' | tail -3
}
trap terminar EXIT

systemctl stop chat-contest-bot

if [ -d auth_info_baileys ]; then
    mv auth_info_baileys "$RESPALDO" || exit 1
    echo "sesion anterior guardada en $BOT/$RESPALDO"
fi

echo
echo "-------------------------------------------------------------"
echo " Escanea el QR con el telefono del numero NUEVO:"
echo "   WhatsApp > Dispositivos vinculados > Vincular un dispositivo"
echo
echo " Cuando el log diga 'conectada como', cortá con Ctrl+C."
echo "-------------------------------------------------------------"
echo

sudo -u contest node index.js
