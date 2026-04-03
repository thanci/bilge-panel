"""
app/xenforo/nodes.py — XenForo Forum Hiyerarşisi Yöneticisi.

XenForo node sistemi:
  Category → içinde forum'lar barındırır (parent gibi)
  Forum    → konu açılabilen ana yapı (Category'nin altında)
  Page     → statik sayfa (bu proje için kullanılmıyor)
  LinkForum → harici link (bu proje için kullanılmıyor)

Bilge Yolcu Kategori Yapısı (örnek, ileride belirlenecek):
  0 (kök)
  ├── Felsefe ve Düşünce [Category]
  │   ├── Antik Felsefe [Forum]
  │   ├── Etik ve Ahlak [Forum]
  │   └── Siyaset Felsefesi [Forum]
  ├── Bilim ve Teknoloji [Category]
  │   ├── Yapay Zeka [Forum]
  │   └── Biyoloji ve Evrim [Forum]
  └── Kültür ve Edebiyat [Category]
      └── ... [Forum]

Bu yapıyı oluşturmak için `create_hierarchy()` metodunu tek bir çağrıyla kullanın.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# XenForo node_type_id sabitleri
NODE_TYPE_FORUM    = "Forum"
NODE_TYPE_CATEGORY = "Category"
NODE_TYPE_PAGE     = "Page"
NODE_TYPE_LINK     = "LinkForum"

# XenForo varsayılan display ayarları
DEFAULT_DISPLAY_IN_LIST = 1   # Kategori listesinde göster
DEFAULT_ALLOW_POSTING   = 1   # Konu açmaya izin ver


class NodeManager:
    """
    XenForo forum düğüm (node) yöneticisi.
    XenForoClient örneğine bağlıdır ve onun üzerinden istekleri gönderir.

    Doğrudan kullanılmaz — client.nodes.xxx() üzerinden erişilir.
    """

    def __init__(self, client):
        self._client = client

    # ─────────────────────────────────────────────────────────
    # OKUMA
    # ─────────────────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """
        Forumun tüm düğümlerini döndürür (düz liste).
        Ağaç yapısı için build_tree() kullanın.

        Returns:
            Node sözlüklerinin listesi:
            [{"node_id": 1, "title": "...", "node_type_id": "Category", ...}]
        """
        resp = self._client.get("nodes")
        return resp.get("nodes", [])

    def get(self, node_id: int) -> dict:
        """Belirli bir node'un detaylarını döndürür."""
        return self._client.get(f"nodes/{node_id}")

    def build_tree(self, nodes: Optional[list] = None) -> list[dict]:
        """
        Düz node listesini ebeveyn-çocuk ağaç yapısına çevirir.

        Dashboard'daki forum seçici ve hiyerarşi görünümü için kullanılır.

        Returns:
            [
                {
                    "node_id": 1, "title": "Felsefe", "type": "Category",
                    "children": [
                        {"node_id": 5, "title": "Antik Felsefe", "type": "Forum", "children": []}
                    ]
                },
                ...
            ]
        """
        if nodes is None:
            nodes = self.list_all()

        # ID → node haritası oluştur
        node_map = {n["node_id"]: {**n, "children": []} for n in nodes}
        roots    = []

        for node in node_map.values():
            parent_id = node.get("parent_node_id", 0)
            if parent_id == 0 or parent_id not in node_map:
                roots.append(node)
            else:
                node_map[parent_id]["children"].append(node)

        return sorted(roots, key=lambda n: n.get("display_order", 0))

    # ─────────────────────────────────────────────────────────
    # OLUŞTURMA
    # ─────────────────────────────────────────────────────────

    def create_forum(
        self,
        name:              str,
        parent_node_id:    int,
        description:       str = "",
        display_order:     int = 10,
        allow_posting:     bool = True,
    ) -> dict:
        """
        Yeni bir Forum düğümü oluşturur.
        Forum = Konu açılabilen alt bölüm.

        Args:
            name:              Forum adı (başlık)
            parent_node_id:    Hangi Category'nin altında? (0 = kök)
            description:       Forum açıklaması (HTML/BB-Code)
            display_order:     Sıralama (düşük = önce)
            allow_posting:     Kullanıcılar bu forumda konu açabilsin mi?

        Returns:
            Oluşturulan node dict'i
        """
        data = {
            "node_name":       name,
            "node_type_id":    NODE_TYPE_FORUM,
            "parent_node_id":  str(parent_node_id),
            "description":     description,
            "display_order":   str(display_order),
            "display_in_list": str(DEFAULT_DISPLAY_IN_LIST),
        }
        resp = self._client.post("nodes", data)
        created = resp.get("node", resp)

        logger.info(
            f"[XF-NODES] Forum oluşturuldu: id={created.get('node_id')} "
            f"name='{name}' parent={parent_node_id}"
        )
        return created

    def create_category(
        self,
        name:           str,
        parent_node_id: int = 0,
        description:    str = "",
        display_order:  int = 10,
    ) -> dict:
        """
        Yeni bir Kategori düğümü oluşturur.
        Kategori = İçinde forum'lar barındıran kapsayıcı.
        Doğrudan konu açılamaz.

        Args:
            name:             Kategori adı
            parent_node_id:   Üst kategori id'si (0 = kök seviyesinde)
            description:      Açıklama
            display_order:    Sıralama

        Returns:
            Oluşturulan node dict'i
        """
        data = {
            "node_name":       name,
            "node_type_id":    NODE_TYPE_CATEGORY,
            "parent_node_id":  str(parent_node_id),
            "description":     description,
            "display_order":   str(display_order),
            "display_in_list": str(DEFAULT_DISPLAY_IN_LIST),
        }
        resp = self._client.post("nodes", data)
        created = resp.get("node", resp)

        logger.info(
            f"[XF-NODES] Kategori oluşturuldu: id={created.get('node_id')} "
            f"name='{name}' parent={parent_node_id}"
        )
        return created

    def create_hierarchy(self, spec: list[dict]) -> list[dict]:
        """
        Ebeveyn-çocuk ilişkisiyle birden fazla node oluşturur (tek çağrı).

        Bu metot Forum Hiyerarşi Planından direkt olarak çağrılabilir.
        Üst kategori oluşturulduktan sonra dönen ID, alt forum'lara aktarılır.

        spec formatı:
        [
            {
                "name":         "Felsefe ve Düşünce",
                "type":         "Category",          # "Category" veya "Forum"
                "parent_id":    0,                   # 0 = kök seviyesi
                "description":  "Felsefi incelemeler",
                "order":        10,
                "children": [
                    {
                        "name":        "Antik Felsefe",
                        "type":        "Forum",
                        "description": "Sokrates, Platon, Aristoteles...",
                        "order":       10,
                    },
                    ...
                ]
            },
        ]

        Returns:
            Oluşturulan tüm node'ların listesi (oluşturulma sırasıyla)
        """
        created_nodes = []
        self._create_nodes_recursive(spec, parent_id=0, results=created_nodes)
        return created_nodes

    def _create_nodes_recursive(
        self,
        nodes:     list[dict],
        parent_id: int,
        results:   list,
    ) -> None:
        """create_hierarchy() için özyinelemeli yardımcı."""
        for i, node_spec in enumerate(nodes):
            node_type   = node_spec.get("type", "Forum").strip()
            name        = node_spec["name"]
            description = node_spec.get("description", "")
            order       = node_spec.get("order", (i + 1) * 10)
            # spec'teki parent_id, recursive çağrıdaki parent_id'yi override eder
            effective_parent = node_spec.get("parent_id", parent_id)

            # Oluştur
            if node_type == "Category":
                created = self.create_category(
                    name           = name,
                    parent_node_id = effective_parent,
                    description    = description,
                    display_order  = order,
                )
            else:  # Forum (varsayılan)
                created = self.create_forum(
                    name           = name,
                    parent_node_id = effective_parent,
                    description    = description,
                    display_order  = order,
                )

            new_id = created.get("node_id")
            results.append(created)

            # Alt düğümleri oluştur (bu node'u parent olarak kullan)
            children = node_spec.get("children", [])
            if children and new_id:
                self._create_nodes_recursive(
                    nodes     = children,
                    parent_id = new_id,
                    results   = results,
                )
