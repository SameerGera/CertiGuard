"""Merkle tree hashing."""

import hashlib
from typing import List, Optional


class MerkleTree:
    def __init__(self):
        self.root = None
        self.leaves = []

    @staticmethod
    def hash_data(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def build(self, records: List[dict]) -> Optional[str]:
        if not records:
            return None

        self.leaves = [self.hash_data(str(r)) for r in records]
        if len(self.leaves) == 1:
            self.root = self.leaves[0]
            return self.root

        while len(self.leaves) > 1:
            if len(self.leaves) % 2:
                self.leaves.append(self.leaves[-1])
            self.leaves = [self.hash_data(self.leaves[i] + self.leaves[i+1]) for i in range(0, len(self.leaves), 2)]

        self.root = self.leaves[0]
        return self.root

    def verify_record(self, record: dict, root: str) -> bool:
        return self.hash_data(str(record)) == root

    def get_root(self) -> Optional[str]:
        return self.root


merkle_tree = MerkleTree()