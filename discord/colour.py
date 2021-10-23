from typing import Type, TypeVar

CT = TypeVar

class Colour:

    @classmethod
    def red(cls: Type[CT]) -> CT:
        return cls(0xe74c3c)


    def green(self, cls: Type[CT]) -> CT:
        return cls(0x2ecc71)