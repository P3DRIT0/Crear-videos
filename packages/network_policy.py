"""Política de sockets Python del proceso: únicamente loopback o sockets Unix."""
import ipaddress
import socket

_originals={}


def local_host(host):
    if isinstance(host,bytes):
        host=host.decode("ascii")
    if isinstance(host,str) and host.lower().rstrip(".")=="localhost":
        return True
    try:
        address=ipaddress.ip_address(host)
        return address.is_loopback or bool(getattr(address,"ipv4_mapped",None) and address.ipv4_mapped.is_loopback)
    except (ValueError,TypeError):
        return False


def require_local(host):
    if not local_host(host):
        raise PermissionError("Modo offline: solo se permiten conexiones loopback.")


def installed():
    return bool(_originals)


def install():
    if installed():
        return
    for name in ("connect","connect_ex","sendto"):
        _originals["socket."+name]=getattr(socket.socket,name)
    for name in ("getaddrinfo","gethostbyname","gethostbyname_ex","gethostbyaddr"):
        _originals[name]=getattr(socket,name)

    def connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            require_local(address[0])
        return _originals["socket.connect"](sock,address)

    def connect_ex(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            require_local(address[0])
        return _originals["socket.connect_ex"](sock,address)

    def sendto(sock,data,*args):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            require_local(args[-1][0])
        return _originals["socket.sendto"](sock,data,*args)

    def getaddrinfo(host,port,*args,**kwargs):
        if host is not None:
            require_local(host)
        result=_originals["getaddrinfo"](host,port,*args,**kwargs)
        flags=kwargs.get("flags",args[3] if len(args)>3 else 0)
        if not flags & socket.AI_PASSIVE:
            for item in result:
                require_local(item[4][0])
        return result

    def resolve(name):
        def guarded(host,*args):
            require_local(host)
            return _originals[name](host,*args)
        return guarded

    socket.socket.connect=connect
    socket.socket.connect_ex=connect_ex
    socket.socket.sendto=sendto
    socket.getaddrinfo=getaddrinfo
    for name in ("gethostbyname","gethostbyname_ex","gethostbyaddr"):
        setattr(socket,name,resolve(name))


def restore():
    """Solo para procesos de pruebas; el runtime no retira su política."""
    for name,original in list(_originals.items()):
        if name.startswith("socket."):
            setattr(socket.socket,name.split(".",1)[1],original)
        else:
            setattr(socket,name,original)
    _originals.clear()
