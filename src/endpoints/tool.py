from typing import List, Optional
from fastapi.responses import StreamingResponse
import loggate
from fastapi import APIRouter, Security
from pydantic import BaseModel
from endpoints import check_token, get_token
from lib.helper import get_qrcode, get_wg_preshared_key, get_wg_private_key, get_wg_public_key, render_template

router = APIRouter(tags=["tool"])
sql_logger = 'sql.peer'
logger = loggate.getLogger('Tool')


class SecretPair(BaseModel):
    private_key: str
    public_key: str


@router.get("/generate_secret_pair", response_model=SecretPair)
async def get_secret_pair(token: bool = Security(get_token)):
    check_token(token)
    priv_key = get_wg_private_key()
    return SecretPair(private_key=priv_key, public_key=get_wg_public_key(priv_key))


class PresharedKey(BaseModel):
    preshared_key: str


@router.get("/generate_preshared_key", response_model=PresharedKey)
async def get_preshared_key(token: bool = Security(get_token)):
    check_token(token)
    return PresharedKey(preshared_key=get_wg_preshared_key())


class GenerateConfigInterface(BaseModel):
    private_key: str
    address: str
    dns: Optional[str]
    fw_mark: Optional[int]
    mtu: Optional[int]
    table: Optional[int]
    pre_up: Optional[str]
    post_up: Optional[str]
    pre_down: Optional[str]
    post_down: Optional[str]


class GenerateConfigPeer(BaseModel):
    public_key: str
    endpoint: Optional[str]
    allowed_ip: Optional[str]
    preshared_key: Optional[str]
    persistent_keepalive: Optional[int]


class GenerateConfig(BaseModel):
    interface: GenerateConfigInterface
    peers: List[GenerateConfigPeer]


@router.post("/generate_client_config", response_model=str)
async def get_client_config(data: GenerateConfig,
                            token: bool = Security(get_token)):
    check_token(token)
    return render_template(
        'client_generator.conf.j2',
        interface=data.interface,
        peers=data.peers
    )


@router.post("/generate_client_qrcode")
async def get_client_qrcode(data: GenerateConfig,
                            token: bool = Security(get_token)):
    check_token(token)
    conf = render_template(
        'client_generator.conf.j2',
        interface=data.interface,
        peers=data.peers
    )
    buffer = get_qrcode(conf)
    return StreamingResponse(buffer, media_type="image/png")
