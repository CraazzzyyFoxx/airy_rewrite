from enum import IntEnum


class HierarchyRoles(IntEnum):
    Missing = 0
    TopDown = 1
    BottomTop = 2

    @classmethod
    def try_value(cls, value):
        for name, value_ in cls._member_map_.items():
            if value_.value == int(value):
                return cls._member_map_[name]
        return value

    @classmethod
    def try_name(cls, value):
        for name, value_ in cls._member_map_.items():
            if name == value:
                return cls._member_map_[name]
        return value


print(HierarchyRoles.try_name("Missing").value)