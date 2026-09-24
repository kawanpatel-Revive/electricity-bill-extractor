"""Registered electricity-provider adapters."""

from .dgvcl import DGVCLParser
from .pgvcl import PGVCLParser
from .torrent import TorrentParser
from .ugvcl import UGVCLParser

PARSERS = (UGVCLParser(), TorrentParser(), PGVCLParser(), DGVCLParser())

__all__ = ["PARSERS"]
