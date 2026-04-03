"""
create_admin.py — İlk yönetici hesabını oluşturma CLI scripti.

Bu script, boş veritabanına ilk admin kullanıcısını ekler.
VPS'e kurulum yaptıktan sonra bir kez çalıştırılır.

Kullanım:
    python create_admin.py
    python create_admin.py --username admin --password gizli123

Güvenlik:
    - Şifre girişi echo olmadan (getpass) yapılır.
    - Mevcut kullanıcıyı silmez, sadece YOKSA oluşturur.
"""

import sys
import argparse
import getpass

# Flask uygulama bağlamını aktif et — modelleri kullanabilmek için
from app import create_app
from app.extensions import db
from app.models import AdminUser


def create_admin_user(username: str, password: str) -> None:
    """
    Verilen kullanıcı adı ve şifreyle admin hesabı oluşturur.
    Eğer aynı kullanıcı adı mevcutsa hata verir.
    """
    app = create_app()
    with app.app_context():
        # Tablo yoksa oluştur (güvenlik ağı)
        db.create_all()

        # Aynı kullanıcı adı var mı?
        existing = AdminUser.query.filter_by(username=username).first()
        if existing:
            print(f"[HATA] '{username}' kullanıcı adı zaten mevcut.")
            print("       Mevcut hesabı güncellemek için doğrudan veritabanını düzenleyin.")
            sys.exit(1)

        # Kullanıcı oluştur
        admin = AdminUser(username=username)
        try:
            admin.set_password(password)
        except ValueError as e:
            print(f"[HATA] {e}")
            sys.exit(1)

        db.session.add(admin)
        db.session.commit()
        print(f"[OK] Admin kullanıcısı oluşturuldu: '{username}' (ID: {admin.id})")
        print("     Artık kontrol paneline giriş yapabilirsiniz.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bilge Yolcu — İlk admin kullanıcısını oluştur"
    )
    parser.add_argument("--username", type=str, help="Admin kullanıcı adı")
    parser.add_argument("--password", type=str, help="Admin şifresi (güvensiz, sadece test için)")

    args = parser.parse_args()

    # Kullanıcı adı argümandan veya interaktif giriş
    username = args.username or input("Kullanıcı adı: ").strip()
    if not username:
        print("[HATA] Kullanıcı adı boş olamaz.")
        sys.exit(1)

    # Şifre argümandan veya güvenli interaktif giriş (echo yok)
    password = args.password
    if not password:
        password = getpass.getpass("Şifre: ")
        confirm  = getpass.getpass("Şifre (tekrar): ")
        if password != confirm:
            print("[HATA] Şifreler eşleşmiyor.")
            sys.exit(1)

    create_admin_user(username, password)
