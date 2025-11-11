import jinja2


class ZabbixHost:
    def __init__(self, host: dict, cfg: dict):
        self._host = host
        self._cfg = cfg

    def hostname(self) -> str:
        """technical host name"""
        return self._host.get("host", "")

    def visiblename(self) -> str:
        """visible name"""
        return self._host.get("name", "")

    def tag(self, tname: str) -> str:
        """get tag value by name"""
        for t in self._host.get("tags", []):
            if t.get("tag") == tname:
                return t.get("value","")
        return ""

    def inventory(self, key: str) -> str:
        """get inventory field"""
        inv = self._host.get("inventory", {})
        if key in inv:
            return inv[key]
        else:
            return ""

    def groups(self) -> str:
        """get host groups"""
        grps = self._host.get("hostgroups", {})
        groups = []
        for g in grps:
            groups.append(g["name"])
        return ",".join(groups)

    def interface(self, key: str) -> str:
        """get IP from interface"""
        if key == "domain":
            dns = self.interface("dns")
            try:
                (host, rest) = dns.split(".", 1)
                if rest and not rest.endswith("."):
                    rest += "."
                return rest
            except Exception:
                return ""
        elif key == "host":
            dns = self.interface("dns")
            try:
                (host, rest) = dns.split(".", 1)
                return host
            except Exception:
                return ""
        else:
            for intf in self._host.get("interfaces", []):
                if intf.get(key):
                    return intf.get(key)
        return ""

    def _matches(self) -> bool:
        """check host matches required filters from cfg."""
        if self._cfg.get("excluded_tags", []):
            for et in self._cfg.get("excluded_tags", ""):
                for t in self._host["tags"]:
                    (name, value) = et.split("=")
                    if t["tag"] == name and t["value"] == value:
                        return False
        if self._cfg.get("excluded_groups", ""):
            for eg in self._cfg.get("excluded_groups", ""):
                for g in self._host["hostgroups"]:
                    if g["name"] == eg:
                        return False
        return True

    def _expand_macros(self, tmpl: str) -> str:
        env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=jinja2.StrictUndefined
        )
        tpl = env.from_string(tmpl)
        expanded = tpl.render(zbx=self)
        return expanded

    @classmethod
    def doc(cls) -> str:
        """list supported macros"""
        lines = ["Available items for zabbix host:"]
        for name in dir(cls):
            if name.startswith("_"):
                continue
            attr = getattr(cls, name)
            if callable(attr):
                doc = attr.__doc__ or ""
                lines.append(f"{name} → {doc}")
        return "\n".join(lines)

    def __getattr__(self, item):
        if item in self._host:
            return self._host[item]
        else:
            print(self.doc())
            raise Exception("Item zbx.%s not found!" % item)

    def __repr__(self):
        return self.hostname()
