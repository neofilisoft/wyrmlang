class WyrmRuntimeError(Exception):
    pass


class Environment:
    __slots__ = ("vars", "consts", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def declare(self, name, value, const=False):
        self.vars[name] = value
        if const:
            self.consts.add(name)
        elif name in self.consts:
            self.consts.discard(name)

    def get(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise WyrmRuntimeError(f"Undefined variable '{name}'")

    def set(self, name, value):
        env = self
        while env is not None:
            if name in env.vars:
                if name in env.consts:
                    raise WyrmRuntimeError(f"Cannot assign to constant '{name}'")
                env.vars[name] = value
                return
            env = env.parent
        # implicit declaration (var keyword is optional per spec)
        self.vars[name] = value

    def has(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False
