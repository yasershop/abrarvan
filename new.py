import os
import sys
import json
import zipfile
import hashlib
import shutil
import smtplib
import secrets
import string
import logging
import subprocess
import importlib
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from cryptography.fernet import Fernet
import boto3
from botocore.client import Config
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QListWidget, QTextEdit,
                            QFileDialog, QMessageBox, QTabWidget, QComboBox, QSpinBox,
                            QInputDialog, QProgressBar, QGroupBox, QCheckBox, QDialog,
                            QDialogButtonBox, QFormLayout)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def نصب_نیازمندی‌ها():
    """نصب خودکار کتابخانه‌های مورد نیاز"""
    کتابخانه‌های_موردنیاز = [
        'PyQt5',
        'boto3',
        'cryptography',
        'botocore'
    ]
    
    for کتابخانه in کتابخانه‌های_موردنیاز:
        try:
            importlib.import_module(کتابخانه.split('.')[0])
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", کتابخانه])
                print(f"کتابخانه {کتابخانه} با موفقیت نصب شد")
            except subprocess.CalledProcessError:
                print(f"خطا در نصب کتابخانه {کتابخانه}")
                return False
    return True

class دیالوگ_بازیابی_رمز(QDialog):
    def __init__(self, نام_کاربری, والد=None):
        super().__init__(والد)
        self.setWindowTitle("تنظیم مجدد رمز عبور")
        self.نام_کاربری = نام_کاربری

        چیدمان = QVBoxLayout()

        فرم = QFormLayout()
        self.رمز_جدید = QLineEdit()
        self.رمز_جدید.setEchoMode(QLineEdit.Password)
        self.تکرار_رمز = QLineEdit()
        self.تکرار_رمز.setEchoMode(QLineEdit.Password)

        فرم.addRow("رمز عبور جدید:", self.رمز_جدید)
        فرم.addRow("تکرار رمز عبور:", self.تکرار_رمز)

        دکمه‌ها = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        دکمه‌ها.accepted.connect(self.اعتبارسنجی)
        دکمه‌ها.rejected.connect(self.reject)

        چیدمان.addLayout(فرم)
        چیدمان.addWidget(دکمه‌ها)
        self.setLayout(چیدمان)

    def اعتبارسنجی(self):
        if self.رمز_جدید.text() != self.تکرار_رمز.text():
            QMessageBox.warning(self, "خطا", "رمزهای عبور مطابقت ندارند!")
            return
        if len(self.رمز_جدید.text()) < 8:
            QMessageBox.warning(self, "خطا", "رمز عبور باید حداقل 8 کاراکتر باشد!")
            return
        self.accept()

class نخ_آپلود(QThread):
    پیشرفت_آپدیت = pyqtSignal(int, str)
    آپلود_تمام = pyqtSignal(bool, str)

    def __init__(self, مسیر_فایل, تنظیمات, logger, رمزنگاری_فایل‌ها=False):
        super().__init__()
        self.مسیر_فایل = مسیر_فایل
        self.تنظیمات = تنظیمات
        self.logger = logger
        self.رمزنگاری_فایل‌ها = رمزنگاری_فایل‌ها
        self.فایل‌های_موقت = []

    def run(self):
        try:
            مسیر_اصلی = self.مسیر_فایل
            مسیر_پردازش = self.مسیر_فایل
            نام_اصلی = os.path.basename(مسیر_اصلی)

            # مرحله 1: فشرده‌سازی اگر فعال باشد
            if self.تنظیمات['فشرده‌سازی_خودکار'] and not مسیر_اصلی.lower().endswith('.zip'):
                مسیر_زیپ = مسیر_اصلی + '.zip'
                self.پیشرفت_آپدیت.emit(10, "در حال فشرده‌سازی فایل...")
                with zipfile.ZipFile(مسیر_زیپ, 'w', zipfile.ZIP_DEFLATED) as زیپ:
                    زیپ.write(مسیر_اصلی, نام_اصلی)
                مسیر_پردازش = مسیر_زیپ
                self.فایل‌های_موقت.append(مسیر_زیپ)
                self.logger.info(f"فایل فشرده شده ایجاد شد: {مسیر_زیپ}")

            # مرحله 2: رمزنگاری اگر فعال باشد
            if self.رمزنگاری_فایل‌ها:
                مسیر_رمزنگاری = مسیر_پردازش + '.enc'
                self.پیشرفت_آپدیت.emit(30, "در حال رمزنگاری فایل...")

                کلید_فایل = self.تنظیمات.get('کلید_رمزنگاری', self.تنظیمات['کلید_فرنت'])
                فرنت = Fernet(کلید_فایل)

                with open(مسیر_پردازش, 'rb') as فایل:
                    داده = فایل.read()

                داده_رمزنگاری = فرنت.encrypt(داده)

                with open(مسیر_رمزنگاری, 'wb') as فایل:
                    فایل.write(داده_رمزنگاری)

                if مسیر_پردازش != مسیر_اصلی:
                    os.remove(مسیر_پردازش)

                مسیر_پردازش = مسیر_رمزنگاری
                self.فایل‌های_موقت.append(مسیر_رمزنگاری)
                self.logger.info(f"فایل رمزنگاری شده ایجاد شد: {مسیر_رمزنگاری}")

            # مرحله 3: آپلود به ابر آروان
            self.پیشرفت_آپدیت.emit(50, "در حال اتصال به سرور...")
            s3 = self.دریافت_کلاینت_s3()
            if not s3:
                self.آپلود_تمام.emit(False, "خطا در اتصال به سرور")
                return

            نام_فایل = os.path.basename(مسیر_پردازش)
            اندازه_فایل = os.path.getsize(مسیر_پردازش)

            def نمایش_پیشرفت(بایت_ارسال):
                درصد = int((بایت_ارسال / اندازه_فایل) * 40) + 50
                self.پیشرفت_آپدیت.emit(درصد, f"در حال آپلود: {درصد-50}%")

            آرگومان‌های_اضافی = {
                'Metadata': {
                    'نام-اصلی': نام_اصلی,
                    'آپلود-توسط': self.تنظیمات.get('کاربر_جاری', 'ناشناس'),
                    'زمان-آپلود': datetime.now().isoformat(),
                    'رمزنگاری': 'بله' if self.رمزنگاری_فایل‌ها else 'خیر',
                    'فشرده': 'بله' if self.تنظیمات['فشرده‌سازی_خودکار'] else 'خیر'
                }
            }

            self.پیشرفت_آپدیت.emit(50, "شروع آپلود...")
            s3.upload_file(
                مسیر_پردازش,
                self.تنظیمات['نام_سطل'],
                نام_فایل,
                ExtraArgs=آرگومان‌های_اضافی,
                Callback=نمایش_پیشرفت
            )

            self.پیشرفت_آپدیت.emit(95, "پایان آپلود...")
            self.آپلود_تمام.emit(True, "آپلود با موفقیت انجام شد")
            self.logger.info(f"فایل {نام_فایل} با موفقیت آپلود شد")

        except Exception as e:
            self.logger.error(f"خطا در آپلود: {str(e)}", exc_info=True)
            self.آپلود_تمام.emit(False, str(e))
        finally:
            # حذف فایل‌های موقت
            for فایل_موقت in self.فایل‌های_موقت:
                if os.path.exists(فایل_موقت):
                    try:
                        os.remove(فایل_موقت)
                    except:
                        pass

    def دریافت_کلاینت_s3(self):
        try:
            return boto3.client(
                's3',
                endpoint_url=self.تنظیمات['آدرس_پایانه'],
                region_name=self.تنظیمات['نام_منطقه'],
                aws_access_key_id=self.تنظیمات['کلید_دسترسی'],
                aws_secret_access_key=self.تنظیمات['کلید_مخفی'],
                config=Config(
                    signature_version='s3v4',
                    connect_timeout=10,
                    retries={'max_attempts': 3}
                )
            )
        except Exception as e:
            self.logger.error(f"خطا در ایجاد اتصال S3: {str(e)}", exc_info=True)
            return None

class آپلودر_امن_آروان(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("آپلودر امن ابر آروان")
        self.setWindowIcon(QIcon("icon.png"))
        self.setGeometry(100, 100, 900, 700)

        # تنظیمات اولیه
        self.فایل_تنظیمات = 'تنظیمات_امن.json'
        self.فایل_کاربران = 'کاربران_امن.json'
        self.کاربر_جاری = None
        self.کلید_فرنت = None
        self.آخرین_آپلود = None

        # راه‌اندازی سیستم‌های پایه
        self.تنظیم_لاگ()
        self.بارگیری_کلید_رمزنگاری()
        self.تنظیمات = self.بارگیری_داده_رمزنگاری(self.فایل_تنظیمات)
        self.کاربران = self.بارگیری_داده_رمزنگاری(self.فایل_کاربران)

        # تنظیمات SMTP برای بازیابی رمز عبور
        self.تنظیمات_smtp = {
            'سرور': 'smtp.example.com',
            'پورت': 587,
            'نام_کاربری': 'your_email@example.com',
            'رمز_عبور': 'your_email_password',
            'ایمیل_فرستنده': 'your_email@example.com',
            'فعال_سازی_tls': True
        }

        # ایجاد فایل‌های اولیه در صورت عدم وجود
        if not self.تنظیمات:
            self.مقداردهی_اولیه_تنظیمات()
        if not self.کاربران:
            self.مقداردهی_اولیه_کاربران()

        # ایجاد رابط کاربری
        self.مقداردهی_ui()

        # تایمر برای آپلود خودکار
        self.تایمر_آپلود_خودکار = QTimer()
        self.تایمر_آپلود_خودکار.timeout.connect(self.بررسی_آپلود_خودکار)

        # پشتیبان‌گیری خودکار
        self.تایمر_پشتیبان = QTimer()
        self.تایمر_پشتیبان.timeout.connect(self.پشتیبان_خودکار)
        self.تایمر_پشتیبان.start(24 * 60 * 60 * 1000)  # هر 24 ساعت

        self.logger.info("برنامه با موفقیت راه‌اندازی شد")

    def تنظیم_لاگ(self):
        """تنظیم سیستم لاگ‌گیری"""
        self.logger = logging.getLogger("آپلودرآروان")
        self.logger.setLevel(logging.DEBUG)

        # ایجاد handler برای ذخیره در فایل
        handler_لاگ = RotatingFileHandler(
            'app.log', maxBytes=1*1024*1024, backupCount=3
        )
        فرمت = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler_لاگ.setFormatter(فرمت)
        self.logger.addHandler(handler_لاگ)

        # همچنین لاگ‌ها را در کنسول نمایش دهید
        handler_کنسول = logging.StreamHandler()
        handler_کنسول.setFormatter(فرمت)
        self.logger.addHandler(handler_کنسول)

    def بارگیری_کلید_رمزنگاری(self):
        فایل_کلید = 'کلید_رمزنگاری.key'
        if os.path.exists(فایل_کلید):
            with open(فایل_کلید, 'rb') as فایل:
                self.کلید_فرنت = فایل.read()
        else:
            self.کلید_فرنت = Fernet.generate_key()
            with open(فایل_کلید, 'wb') as فایل:
                فایل.write(self.کلید_فرنت)

        # اطمینان حاصل کنید که کلید در تنظیمات نیز وجود دارد
        if 'کلید_فرنت' not in self.تنظیمات:
            self.تنظیمات['کلید_فرنت'] = self.کلید_فرنت
            self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات)

    def رمزنگاری_داده(self, داده):
        if isinstance(داده, str):
            داده = داده.encode()
        return Fernet(self.کلید_فرنت).encrypt(داده).decode()

    def رمزگشایی_داده(self, داده_رمزنگاری):
        if isinstance(داده_رمزنگاری, str):
            داده_رمزنگاری = داده_رمزنگاری.encode()
        return Fernet(self.کلید_فرنت).decrypt(داده_رمزنگاری).decode()

    def بارگیری_داده_رمزنگاری(self, نام_فایل):
        try:
            with open(نام_فایل, 'r') as فایل:
                داده_رمزنگاری = json.load(فایل)
            داده_رمزگشایی = json.loads(self.رمزگشایی_داده(داده_رمزنگاری['داده']))
            self.logger.info(f"فایل {نام_فایل} با موفقیت بارگیری شد")
            return داده_رمزگشایی
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.logger.warning(f"فایل {نام_فایل} یافت نشد یا معتبر نیست")
            return {}
        except Exception as e:
            self.logger.error(f"خطا در بارگیری فایل {نام_فایل}: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "خطا", f"خطا در بارگیری فایل {نام_فایل}: {str(e)}")
            return {}

    def ذخیره_داده_رمزنگاری(self, نام_فایل, داده):
        try:
            داده_رمزنگاری = {
                'داده': self.رمزنگاری_داده(json.dumps(داده))
            }
            with open(نام_فایل, 'w') as فایل:
                json.dump(داده_رمزنگاری, فایل, indent=4)
            self.logger.info(f"فایل {نام_فایل} با موفقیت ذخیره شد")
            return True
        except Exception as e:
            self.logger.error(f"خطا در ذخیره فایل {نام_فایل}: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "خطا", f"خطا در ذخیره فایل {نام_فایل}: {str(e)}")
            return False

    def مقداردهی_اولیه_تنظیمات(self):
        تنظیمات_پیش‌فرض = {
            'آدرس_پایانه': 'https://s3.ir-thr-at1.arvanstorage.com',
            'نام_منطقه': 'ir-thr-at1',
            'کلید_دسترسی': '',
            'کلید_مخفی': '',
            'نام_سطل': '',
            'پوشه_نظارت': os.path.expanduser('~'),
            'فاصله_آپلود': 60,
            'فشرده‌سازی_خودکار': True,
            'نگهداری_کپی_محلی': False,
            'حداکثر_پشتیبان': 5,
            'رمزنگاری_فایل‌ها': True,
            'کلید_فرنت': self.کلید_فرنت,
            'کاربر_جاری': None,
            'تنظیمات_smtp': self.تنظیمات_smtp
        }
        self.تنظیمات = تنظیمات_پیش‌فرض
        self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات)
        self.logger.info("تنظیمات اولیه ایجاد شد")

    def مقداردهی_اولیه_کاربران(self):
        کاربران_پیش‌فرض = {
            'admin': {
                'رمز_عبور': self.هش_رمز('admin123'),
                'نقش': 'مدیر',
                'ایمیل': 'admin@example.com',
                'توکن_بازیابی': None,
                'انقضای_توکن': None
            }
        }
        self.کاربران = کاربران_پیش‌فرض
        self.ذخیره_داده_رمزنگاری(self.فایل_کاربران, self.کاربران)
        self.logger.info("کاربران اولیه ایجاد شد")

    def هش_رمز(self, رمز):
        return hashlib.sha256(رمز.encode()).hexdigest()

    def مقداردهی_ui(self):
        # تب‌های اصلی
        self.تب‌ها = QTabWidget()
        self.تب‌ها.setTabPosition(QTabWidget.West)
        self.تب‌ها.setMovable(True)
        self.تب‌ها.setStyleSheet("""
        QTabBar::tab {
            padding: 10px;
            margin-right: 5px;
            border-radius: 5px;
        }
        QTabBar::tab:selected {
            background: #2b5b84;
            color: white;
        }
        """)

        # تب لاگین
        self.تب_لاگین = QWidget()
        self.مقداردهی_تب_لاگین()
        self.تب‌ها.addTab(self.تب_لاگین, "ورود به سیستم")

        # تب‌های دیگر (در ابتدا غیرفعال)
        self.تب_اصلی = QWidget()
        self.تب_آپلود = QWidget()
        self.تب_مدیریت = QWidget()
        self.تب_تنظیمات = QWidget()
        self.تب_کاربران = QWidget()

        self.setCentralWidget(self.تب‌ها)

        # نوار وضعیت
        self.statusBar().showMessage("آماده به کار")

    def مقداردهی_تب_لاگین(self):
        چیدمان = QVBoxLayout()

        # عنوان
        عنوان = QLabel("آپلودر امن ابر آروان")
        عنوان.setFont(QFont("Arial", 16, QFont.Bold))
        عنوان.setAlignment(Qt.AlignCenter)
        چیدمان.addWidget(عنوان)

        # فیلدهای ورود
        چیدمان_فرم = QVBoxLayout()

        self.ورودی_نام_کاربری = QLineEdit()
        self.ورودی_نام_کاربری.setPlaceholderText("نام کاربری")
        چیدمان_فرم.addWidget(self.ورودی_نام_کاربری)

        self.ورودی_رمز = QLineEdit()
        self.ورودی_رمز.setPlaceholderText("رمز عبور")
        self.ورودی_رمز.setEchoMode(QLineEdit.Password)
        چیدمان_فرم.addWidget(self.ورودی_رمز)

        # لینک بازیابی رمز عبور
        فراموشی_رمز = QPushButton("رمز عبور را فراموش کرده‌ام")
        فراموشی_رمز.setStyleSheet("color: blue; text-decoration: underline; border: none;")
        فراموشی_رمز.setCursor(Qt.PointingHandCursor)
        فراموشی_رمز.clicked.connect(self.نمایش_دیالوگ_فراموشی_رمز)
        چیدمان_فرم.addWidget(فراموشی_رمز)

        دکمه_ورود = QPushButton("ورود")
        دکمه_ورود.clicked.connect(self.احراز_هویت)
        چیدمان_فرم.addWidget(دکمه_ورود)

        چیدمان.addLayout(چیدمان_فرم)
        self.تب_لاگین.setLayout(چیدمان)

    def نمایش_دیالوگ_فراموشی_رمز(self):
        دیالوگ = QDialog(self)
        دیالوگ.setWindowTitle("بازیابی رمز عبور")

        چیدمان = QVBoxLayout()

        فرم = QFormLayout()
        self.نام_کاربری_بازیابی = QLineEdit()
        self.ایمیل_بازیابی = QLineEdit()

        فرم.addRow("نام کاربری:", self.نام_کاربری_بازیابی)
        فرم.addRow("ایمیل ثبت‌شده:", self.ایمیل_بازیابی)

        دکمه‌ها = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        دکمه‌ها.accepted.connect(lambda: self.پردازش_بازیابی_رمز(دیالوگ))
        دکمه‌ها.rejected.connect(دیالوگ.reject)

        چیدمان.addLayout(فرم)
        چیدمان.addWidget(دکمه‌ها)
        دیالوگ.setLayout(چیدمان)
        دیالوگ.exec_()

    def پردازش_بازیابی_رمز(self, دیالوگ):
        نام_کاربری = self.نام_کاربری_بازیابی.text()
        ایمیل = self.ایمیل_بازیابی.text()

        if not نام_کاربری or not ایمیل:
            QMessageBox.warning(self, "خطا", "لطفاً تمام فیلدها را پر کنید!")
            return

        if نام_کاربری not in self.کاربران:
            QMessageBox.warning(self, "خطا", "نام کاربری یافت نشد!")
            return

        if 'ایمیل' not in self.کاربران[نام_کاربری] or self.کاربران[نام_کاربری]['ایمیل'].lower() != ایمیل.lower():
            QMessageBox.warning(self, "خطا", "ایمیل با ایمیل ثبت‌شده مطابقت ندارد!")
            return

        self.ارسال_ایمیل_بازیابی(نام_کاربری, ایمیل)
        QMessageBox.information(self, "موفق", "ایمیل بازیابی رمز عبور ارسال شد!")
        دیالوگ.accept()

    def احراز_هویت(self):
        نام_کاربری = self.ورودی_نام_کاربری.text()
        رمز = self.ورودی_رمز.text()

        if نام_کاربری in self.کاربران and self.کاربران[نام_کاربری]['رمز_عبور'] == self.هش_رمز(رمز):
            self.کاربر_جاری = نام_کاربری
            self.تنظیمات['کاربر_جاری'] = نام_کاربری
            self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات)

            self.statusBar().showMessage(f"خوش آمدید {نام_کاربری}!")
            self.logger.info(f"کاربر {نام_کاربری} با موفقیت وارد شد")

            # نمایش نوتیفیکیشن
            self.نمایش_اطلاعیه("ورود موفق", f"خوش آمدید {نام_کاربری}")

            # فعال کردن تب‌های دیگر
            self.مقداردهی_تب‌های_اصلی()
            self.تب‌ها.removeTab(0)  # حذف تب لاگین
        else:
            QMessageBox.warning(self, "خطا", "نام کاربری یا رمز عبور اشتباه است!")
            self.logger.warning(f"تلاش ناموفق برای ورود با نام کاربری {نام_کاربری}")

    def مقداردهی_تب‌های_اصلی(self):
        # تب اصلی
        self.مقداردهی_تب_اصلی()
        self.تب‌ها.addTab(self.تب_اصلی, "صفحه اصلی")

        # تب آپلود
        self.مقداردهی_تب_آپلود()
        self.تب‌ها.addTab(self.تب_آپلود, "آپلود فایل")

        # تب مدیریت فایل‌ها
        self.مقداردهی_تب_مدیریت()
        self.تب‌ها.addTab(self.تب_مدیریت, "مدیریت فایل‌ها")

        # تب تنظیمات
        self.مقداردهی_تب_تنظیمات()
        self.تب‌ها.addTab(self.تب_تنظیمات, "تنظیمات")

        # تب کاربران (فقط برای ادمین)
        if self.کاربران[self.کاربر_جاری]['نقش'] == 'مدیر':
            self.مقداردهی_تب_کاربران()
            self.تب‌ها.addTab(self.تب_کاربران, "مدیریت کاربران")

    def مقداردهی_تب_اصلی(self):
        چیدمان = QVBoxLayout()

        خوشآمد = QLabel(f"خوش آمدید {self.کاربر_جاری}!")
        خوشآمد.setFont(QFont("Arial", 14))
        خوشآمد.setAlignment(Qt.AlignCenter)
        چیدمان.addWidget(خوشآمد)

        اطلاعات = QLabel("""
        <p>این برنامه برای آپلود ایمن فایل‌ها به ابر آروان طراحی شده است.</p>
        <p>امکانات:</p>
        <ul>
            <li>آپلود خودکار آخرین فایل در دایرکتوری مشخص</li>
            <li>تبدیل به ZIP قبل از آپلود</li>
            <li>رمزنگاری فایل‌ها قبل از آپلود</li>
            <li>مدیریت فایل‌های آپلود شده</li>
            <li>تنظیمات پیشرفته</li>
            <li>رمزنگاری اطلاعات حساس</li>
            <li>سیستم لاگ‌گیری پیشرفته</li>
            <li>پشتیبان‌گیری خودکار</li>
            <li>مدیریت کاربران و بازیابی رمز عبور</li>
        </ul>
        """)
        اطلاعات.setWordWrap(True)
        چیدمان.addWidget(اطلاعات)

        # وضعیت اتصال
        وضعیت_اتصال = QLabel("وضعیت اتصال: " + ("متصل" if self.تست_اتصال() else "قطع"))
        وضعیت_اتصال.setStyleSheet("color: " + ("green" if self.تست_اتصال() else "red"))
        چیدمان.addWidget(وضعیت_اتصال)

        # نمایش آخرین لاگ‌ها
        نمایشگر_لاگ = QTextEdit()
        نمایشگر_لاگ.setReadOnly(True)
        نمایشگر_لاگ.setMaximumHeight(150)

        # خواندن آخرین خطوط فایل لاگ
        try:
            with open('app.log', 'r') as فایل:
                خطوط = فایل.readlines()[-10:]  # 10 خط آخر
                نمایشگر_لاگ.setText(''.join(خطوط))
        except:
            نمایشگر_لاگ.setText("فایل لاگ یافت نشد")

        چیدمان.addWidget(QLabel("آخرین رویدادها:"))
        چیدمان.addWidget(نمایشگر_لاگ)

        self.تب_اصلی.setLayout(چیدمان)

    def مقداردهی_تب_آپلود(self):
        چیدمان = QVBoxLayout()

        # تنظیمات آپلود خودکار
        گروه_خودکار = QWidget()
        چیدمان_خودکار = QVBoxLayout()

        عنوان_خودکار = QLabel("آپلود خودکار")
        عنوان_خودکار.setFont(QFont("Arial", 12, QFont.Bold))
        چیدمان_خودکار.addWidget(عنوان_خودکار)

        self.دکمه_آپلود_خودکار = QPushButton("شروع آپلود خودکار")
        self.دکمه_آپلود_خودکار.clicked.connect(self.تغییر_حالت_آپلود_خودکار)
        چیدمان_خودکار.addWidget(self.دکمه_آپلود_خودکار)

        self.برچسب_وضعیت = QLabel("وضعیت: غیرفعال")
        چیدمان_خودکار.addWidget(self.برچسب_وضعیت)

        گروه_خودکار.setLayout(چیدمان_خودکار)
        چیدمان.addWidget(گروه_خودکار)

        # آپلود دستی
        گروه_دستی = QWidget()
        چیدمان_دستی = QVBoxLayout()

        عنوان_دستی = QLabel("آپلود دستی")
        عنوان_دستی.setFont(QFont("Arial", 12, QFont.Bold))
        چیدمان_دستی.addWidget(عنوان_دستی)

        self.برچسب_مسیر_فایل = QLabel("فایلی انتخاب نشده است")
        چیدمان_دستی.addWidget(self.برچسب_مسیر_فایل)

        دکمه_مرور = QPushButton("انتخاب فایل")
        دکمه_مرور.clicked.connect(self.مرور_فایل)
        چیدمان_دستی.addWidget(دکمه_مرور)

        دکمه_آپلود = QPushButton("آپلود فایل")
        دکمه_آپلود.clicked.connect(self.آپلود_دستی)
        چیدمان_دستی.addWidget(دکمه_آپلود)

        self.نوار_پیشرفت = QProgressBar()
        چیدمان_دستی.addWidget(self.نوار_پیشرفت)

        self.برچسب_پیشرفت = QLabel("آماده برای آپلود")
        چیدمان_دستی.addWidget(self.برچسب_پیشرفت)

        self.جزئیات_پیشرفت = QLabel("")
        چیدمان_دستی.addWidget(self.جزئیات_پیشرفت)

        گروه_دستی.setLayout(چیدمان_دستی)
        چیدمان.addWidget(گروه_دستی)

        self.تب_آپلود.setLayout(چیدمان)

    def مقداردهی_تب_مدیریت(self):
        چیدمان = QVBoxLayout()

        # جستجو
        self.جعبه_جستجو = QLineEdit()
        self.جعبه_جستجو.setPlaceholderText("جستجو در فایل‌ها...")
        self.جعبه_جستجو.textChanged.connect(self.فیلتر_فایل‌ها)
        چیدمان.addWidget(self.جعبه_جستجو)

        # لیست فایل‌ها
        self.لیست_فایل‌ها = QListWidget()
        self.لیست_فایل‌ها.setSelectionMode(QListWidget.ExtendedSelection)
        self.بروزرسانی_لیست_فایل‌ها()
        چیدمان.addWidget(self.لیست_فایل‌ها)

        # دکمه‌های مدیریت
        چیدمان_دکمه‌ها = QHBoxLayout()

        دکمه_بروزرسانی = QPushButton("بروزرسانی لیست")
        دکمه_بروزرسانی.clicked.connect(self.بروزرسانی_لیست_فایل‌ها)
        چیدمان_دکمه‌ها.addWidget(دکمه_بروزرسانی)

        دکمه_دانلود = QPushButton("دانلود")
        دکمه_دانلود.clicked.connect(self.دانلود_فایل)
        چیدمان_دکمه‌ها.addWidget(دکمه_دانلود)

        دکمه_حذف = QPushButton("حذف")
        دکمه_حذف.clicked.connect(self.حذف_فایل)
        چیدمان_دکمه‌ها.addWidget(دکمه_حذف)

        چیدمان.addLayout(چیدمان_دکمه‌ها)

        self.تب_مدیریت.setLayout(چیدمان)

    def مقداردهی_تب_تنظیمات(self):
        چیدمان = QVBoxLayout()

        # تنظیمات اتصال
        گروه_اتصال = QGroupBox("تنظیمات اتصال")
        چیدمان_اتصال = QVBoxLayout()

        self.ورودی_آدرس_پایانه = QLineEdit(self.تنظیمات['آدرس_پایانه'])
        self.ورودی_آدرس_پایانه.setPlaceholderText("آدرس پایانه")
        چیدمان_اتصال.addWidget(self.ورودی_آدرس_پایانه)

        self.ورودی_نام_منطقه = QLineEdit(self.تنظیمات['نام_منطقه'])
        self.ورودی_نام_منطقه.setPlaceholderText("نام منطقه")
        چیدمان_اتصال.addWidget(self.ورودی_نام_منطقه)

        self.ورودی_کلید_دسترسی = QLineEdit(self.تنظیمات['کلید_دسترسی'])
        self.ورودی_کلید_دسترسی.setPlaceholderText("کلید دسترسی")
        چیدمان_اتصال.addWidget(self.ورودی_کلید_دسترسی)

        self.ورودی_کلید_مخفی = QLineEdit(self.تنظیمات['کلید_مخفی'])
        self.ورودی_کلید_مخفی.setPlaceholderText("کلید مخفی")
        self.ورودی_کلید_مخفی.setEchoMode(QLineEdit.Password)
        چیدمان_اتصال.addWidget(self.ورودی_کلید_مخفی)

        self.ورودی_نام_سطل = QLineEdit(self.تنظیمات['نام_سطل'])
        self.ورودی_نام_سطل.setPlaceholderText("نام سطل")
        چیدمان_اتصال.addWidget(self.ورودی_نام_سطل)

        دکمه_تست = QPushButton("تست اتصال")
        دکمه_تست.clicked.connect(self.تست_اتصال_ui)
        چیدمان_اتصال.addWidget(دکمه_تست)

        گروه_اتصال.setLayout(چیدمان_اتصال)
        چیدمان.addWidget(گروه_اتصال)

        # تنظیمات آپلود
        گروه_آپلود = QGroupBox("تنظیمات آپلود")
        چیدمان_آپلود = QVBoxLayout()

        self.برچسب_پوشه_نظارت = QLabel(self.تنظیمات['پوشه_نظارت'])
        چیدمان_آپلود.addWidget(self.برچسب_پوشه_نظارت)

        دکمه_تغییر = QPushButton("تغییر دایرکتوری نظارت")
        دکمه_تغییر.clicked.connect(self.تغییر_پوشه_نظارت)
        چیدمان_آپلود.addWidget(دکمه_تغییر)

        self.اسپین_فاصله = QSpinBox()
        self.اسپین_فاصله.setRange(10, 3600)
        self.اسپین_فاصله.setValue(self.تنظیمات['فاصله_آپلود'])
        self.اسپین_فاصله.setSuffix(" ثانیه")
        چیدمان_آپلود.addWidget(QLabel("فاصله بررسی:"))
        چیدمان_آپلود.addWidget(self.اسپین_فاصله)

        self.کامبوباکس_فشرده‌سازی = QComboBox()
        self.کامبوباکس_فشرده‌سازی.addItems(["فشرده‌سازی خودکار فعال", "فشرده‌سازی خودکار غیرفعال"])
        self.کامبوباکس_فشرده‌سازی.setCurrentIndex(0 if self.تنظیمات['فشرده‌سازی_خودکار'] else 1)
        چیدمان_آپلود.addWidget(self.کامبوباکس_فشرده‌سازی)

        self.کامبوباکس_کپی_محلی = QComboBox()
        self.کامبوباکس_کپی_محلی.addItems(["نگهداری کپی محلی فعال", "نگهداری کپی محلی غیرفعال"])
        self.کامبوباکس_کپی_محلی.setCurrentIndex(0 if self.تنظیمات['نگهداری_کپی_محلی'] else 1)
        چیدمان_آپلود.addWidget(self.کامبوباکس_کپی_محلی)

        self.اسپین_حداکثر_پشتیبان = QSpinBox()
        self.اسپین_حداکثر_پشتیبان.setRange(1, 100)
        self.اسپین_حداکثر_پشتیبان.setValue(self.تنظیمات['حداکثر_پشتیبان'])
        چیدمان_آپلود.addWidget(QLabel("حداکثر تعداد نسخه‌های پشتیبان:"))
        چیدمان_آپلود.addWidget(self.اسپین_حداکثر_پشتیبان)

        گروه_آپلود.setLayout(چیدمان_آپلود)
        چیدمان.addWidget(گروه_آپلود)

        # تنظیمات رمزنگاری
        گروه_رمزنگاری = QGroupBox("تنظیمات رمزنگاری")
        چیدمان_رمزنگاری = QVBoxLayout()

        self.کامبوباکس_رمزنگاری = QComboBox()
        self.کامبوباکس_رمزنگاری.addItems(["رمزنگاری فایل‌ها فعال", "رمزنگاری فایل‌ها غیرفعال"])
        self.کامبوباکس_رمزنگاری.setCurrentIndex(0 if self.تنظیمات['رمزنگاری_فایل‌ها'] else 1)
        چیدمان_رمزنگاری.addWidget(self.کامبوباکس_رمزنگاری)

        دکمه_تولید_کلید = QPushButton("تولید کلید جدید")
        دکمه_تولید_کلید.clicked.connect(self.تولید_کلید_جدید)
        چیدمان_رمزنگاری.addWidget(دکمه_تولید_کلید)

        گروه_رمزنگاری.setLayout(چیدمان_رمزنگاری)
        چیدمان.addWidget(گروه_رمزنگاری)

        # تنظیمات SMTP
        گروه_smtp = QGroupBox("تنظیمات SMTP (برای بازیابی رمز عبور)")
        چیدمان_smtp = QVBoxLayout()

        self.ورودی_سرور_smtp = QLineEdit(self.تنظیمات_smtp['سرور'])
        چیدمان_smtp.addWidget(QLabel("سرور SMTP:"))
        چیدمان_smtp.addWidget(self.ورودی_سرور_smtp)

        self.ورودی_پورت_smtp = QLineEdit(str(self.تنظیمات_smtp['پورت']))
        چیدمان_smtp.addWidget(QLabel("پورت:"))
        چیدمان_smtp.addWidget(self.ورودی_پورت_smtp)

        self.ورودی_کاربر_smtp = QLineEdit(self.تنظیمات_smtp['نام_کاربری'])
        چیدمان_smtp.addWidget(QLabel("نام کاربری:"))
        چیدمان_smtp.addWidget(self.ورودی_کاربر_smtp)

        self.ورودی_رمز_smtp = QLineEdit(self.تنظیمات_smtp['رمز_عبور'])
        self.ورودی_رمز_smtp.setEchoMode(QLineEdit.Password)
        چیدمان_smtp.addWidget(QLabel("رمز عبور:"))
        چیدمان_smtp.addWidget(self.ورودی_رمز_smtp)

        self.ورودی_فرستنده_smtp = QLineEdit(self.تنظیمات_smtp['ایمیل_فرستنده'])
        چیدمان_smtp.addWidget(QLabel("ایمیل فرستنده:"))
        چیدمان_smtp.addWidget(self.ورودی_فرستنده_smtp)

        self.چک_باکس_tls = QCheckBox("فعال کردن TLS")
        self.چک_باکس_tls.setChecked(self.تنظیمات_smtp.get('فعال_سازی_tls', True))
        چیدمان_smtp.addWidget(self.چک_باکس_tls)

        دکمه_تست_smtp = QPushButton("تست اتصال SMTP")
        دکمه_تست_smtp.clicked.connect(self.تست_اتصال_smtp)
        چیدمان_smtp.addWidget(دکمه_تست_smtp)

        گروه_smtp.setLayout(چیدمان_smtp)
        چیدمان.addWidget(گروه_smtp)

        # دکمه ذخیره
        دکمه_ذخیره = QPushButton("ذخیره تنظیمات")
        دکمه_ذخیره.clicked.connect(self.ذخیره_تنظیمات)
        چیدمان.addWidget(دکمه_ذخیره)

        self.تب_تنظیمات.setLayout(چیدمان)

    def مقداردهی_تب_کاربران(self):
        چیدمان = QVBoxLayout()

        # گروه مدیریت کاربران
        گروه_مدیریت = QGroupBox("مدیریت کاربران")
        چیدمان_مدیریت = QVBoxLayout()

        self.لیست_کاربران = QListWidget()
        self.بروزرسانی_لیست_کاربران()
        چیدمان_مدیریت.addWidget(self.لیست_کاربران)

        # دکمه‌های مدیریت
        چیدمان_دکمه‌ها = QHBoxLayout()

        دکمه_افزودن = QPushButton("افزودن کاربر")
        دکمه_افزودن.clicked.connect(self.افزودن_کاربر)
        چیدمان_دکمه‌ها.addWidget(دکمه_افزودن)

        دکمه_ویرایش = QPushButton("ویرایش")
        دکمه_ویرایش.clicked.connect(self.ویرایش_کاربر)
        چیدمان_دکمه‌ها.addWidget(دکمه_ویرایش)

        دکمه_حذف = QPushButton("حذف")
        دکمه_حذف.clicked.connect(self.حذف_کاربر)
        چیدمان_دکمه‌ها.addWidget(دکمه_حذف)

        چیدمان_مدیریت.addLayout(چیدمان_دکمه‌ها)
        گروه_مدیریت.setLayout(چیدمان_مدیریت)
        چیدمان.addWidget(گروه_مدیریت)

        # گروه حساب کاربری فعلی
        گروه_کاربر_جاری = QGroupBox("حساب کاربری فعلی")
        چیدمان_کاربر_جاری = QVBoxLayout()

        self.برچسب_کاربر_جاری = QLabel(f"کاربر فعلی: {self.کاربر_جاری}")
        چیدمان_کاربر_جاری.addWidget(self.برچسب_کاربر_جاری)

        دکمه_تغییر_رمز = QPushButton("تغییر رمز عبور")
        دکمه_تغییر_رمز.clicked.connect(self.تغییر_رمز_خود)
        چیدمان_کاربر_جاری.addWidget(دکمه_تغییر_رمز)

        دکمه_تغییر_ایمیل = QPushButton("تغییر ایمیل")
        دکمه_تغییر_ایمیل.clicked.connect(self.تغییر_ایمیل_خود)
        چیدمان_کاربر_جاری.addWidget(دکمه_تغییر_ایمیل)

        گروه_کاربر_جاری.setLayout(چیدمان_کاربر_جاری)
        چیدمان.addWidget(گروه_کاربر_جاری)

        # گروه بازیابی رمز عبور
        گروه_بازیابی = QGroupBox("بازیابی رمز عبور")
        چیدمان_بازیابی = QVBoxLayout()

        self.ورودی_ایمیل_بازیابی = QLineEdit()
        self.ورودی_ایمیل_بازیابی.setPlaceholderText("ایمیل کاربر")
        چیدمان_بازیابی.addWidget(self.ورودی_ایمیل_بازیابی)

        دکمه_ارسال_لینک = QPushButton("ارسال لینک بازیابی")
        دکمه_ارسال_لینک.clicked.connect(self.ارسال_ایمیل_بازیابی)
        چیدمان_بازیابی.addWidget(دکمه_ارسال_لینک)

        گروه_بازیابی.setLayout(چیدمان_بازیابی)
        چیدمان.addWidget(گروه_بازیابی)

        self.تب_کاربران.setLayout(چیدمان)

    def تغییر_حالت_آپلود_خودکار(self):
        if self.تایمر_آپلود_خودکار.isActive():
            self.تایمر_آپلود_خودکار.stop()
            self.دکمه_آپلود_خودکار.setText("شروع آپلود خودکار")
            self.برچسب_وضعیت.setText("وضعیت: غیرفعال")
            self.statusBar().showMessage("آپلود خودکار متوقف شد")
            self.logger.info("آپلود خودکار متوقف شد")
        else:
            فاصله = self.تنظیمات['فاصله_آپلود'] * 1000  # تبدیل به میلی‌ثانیه
            self.تایمر_آپلود_خودکار.start(فاصله)
            self.دکمه_آپلود_خودکار.setText("توقف آپلود خودکار")
            self.برچسب_وضعیت.setText(f"وضعیت: فعال (هر {self.تنظیمات['فاصله_آپلود']} ثانیه)")
            self.statusBar().showMessage("آپلود خودکار شروع شد")
            self.logger.info(f"آپلود خودکار شروع شد - فاصله بررسی: {self.تنظیمات['فاصله_آپلود']} ثانیه")
            self.بررسی_آپلود_خودکار()  # بررسی فوری

    def بررسی_آپلود_خودکار(self):
        پوشه_نظارت = self.تنظیمات['پوشه_نظارت']
        if not os.path.isdir(پوشه_نظارت):
            self.statusBar().showMessage(f"خطا: دایرکتوری {پوشه_نظارت} وجود ندارد!")
            self.logger.error(f"دایرکتوری نظارت وجود ندارد: {پوشه_نظارت}")
            return

        فایل‌ها = [ف for ف in os.listdir(پوشه_نظارت) if os.path.isfile(os.path.join(پوشه_نظارت, ف))]
        if not فایل‌ها:
            return

        # فیلتر کردن فایل‌هایی که قبلاً آپلود شده‌اند
        فایل‌های_جدید = [ف for ف in فایل‌ها if not self.آخرین_آپلود or 
                    datetime.fromtimestamp(os.path.getmtime(os.path.join(پوشه_نظارت, ف))) > self.آخرین_آپلود]

        if فایل‌های_جدید:
            # آپلود جدیدترین فایل
            جدیدترین_فایل = max(فایل‌های_جدید, key=lambda ف: os.path.getmtime(os.path.join(پوشه_نظارت, ف)))
            مسیر_فایل = os.path.join(پوشه_نظارت, جدیدترین_فایل)
            self.آخرین_آپلود = datetime.now()
            self.آپلود_فایل(مسیر_فایل)

    def آپلود_فایل(self, مسیر_فایل):
        """آپلود فایل به ابر آروان با نمایش پیشرفت"""
        self.نوار_پیشرفت.setValue(0)
        self.برچسب_پیشرفت.setText("آماده سازی فایل برای آپلود...")
        
        # ایجاد و شروع نخ آپلود
        self.نخ_آپلود = نخ_آپلود(
            مسیر_فایل,
            self.تنظیمات,
            self.logger,
            self.تنظیمات['رمزنگاری_فایل‌ها']
        )
        
        # اتصال سیگنال‌ها
        self.نخ_آپلود.پیشرفت_آپدیت.connect(self.به‌روزرسانی_پیشرفت)
        self.نخ_آپلود.آپلود_تمام.connect(self.اتمام_آپلود)
        
        self.نخ_آپلود.start()

    def به‌روزرسانی_پیشرفت(self, درصد, پیام):
        self.نوار_پیشرفت.setValue(درصد)
        self.جزئیات_پیشرفت.setText(پیام)

    def اتمام_آپلود(self, موفقیت, پیام):
        if موفقیت:
            QMessageBox.information(self, "موفقیت", پیام)
            self.statusBar().showMessage("آپلود با موفقیت انجام شد")
            self.بروزرسانی_لیست_فایل‌ها()
        else:
            QMessageBox.warning(self, "خطا", پیام)
            self.statusBar().showMessage("خطا در آپلود فایل")
        
        self.برچسب_پیشرفت.setText("آپلود کامل شد")
        self.نوار_پیشرفت.setValue(100)

    def آپلود_دستی(self):
        if not hasattr(self, 'فایل_انتخابی') or not self.فایل_انتخابی:
            QMessageBox.warning(self, "خطا", "لطفاً ابتدا یک فایل انتخاب کنید")
            return
        
        self.آپلود_فایل(self.فایل_انتخابی)

    def مرور_فایل(self):
        مسیر_فایل, _ = QFileDialog.getOpenFileName(
            self, 
            "انتخاب فایل برای آپلود", 
            self.تنظیمات['پوشه_نظارت'],
            "همه فایل‌ها (*.*)"
        )
        
        if مسیر_فایل:
            self.فایل_انتخابی = مسیر_فایل
            self.برچسب_مسیر_فایل.setText(os.path.basename(مسیر_فایل))
            self.برچسب_پیشرفت.setText("آماده برای آپلود")

    def بروزرسانی_لیست_فایل‌ها(self):
        """بروزرسانی لیست فایل‌های موجود در سطل"""
        try:
            s3 = self.دریافت_کلاینت_s3()
            if not s3:
                QMessageBox.warning(self, "خطا", "اتصال به سرور برقرار نشد")
                return

            self.لیست_فایل‌ها.clear()
            پاسخ = s3.list_objects_v2(Bucket=self.تنظیمات['نام_سطل'])
            
            if 'Contents' in پاسخ:
                for مورد in پاسخ['Contents']:
                    self.لیست_فایل‌ها.addItem(مورد['Key'])
            
            self.statusBar().showMessage(f"{self.لیست_فایل‌ها.count()} فایل یافت شد")
            self.logger.info("لیست فایل‌ها با موفقیت بروزرسانی شد")
        except Exception as e:
            self.logger.error(f"خطا در دریافت لیست فایل‌ها: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "خطا", f"خطا در دریافت لیست فایل‌ها: {str(e)}")

    def فیلتر_فایل‌ها(self):
        متن_جستجو = self.جعبه_جستجو.text().lower()
        for i in range(self.لیست_فایل‌ها.count()):
            مورد = self.لیست_فایل‌ها.item(i)
            مورد.setHidden(متن_جستجو not in مورد.text().lower())

    def دانلود_فایل(self):
        موارد_انتخابی = self.لیست_فایل‌ها.selectedItems()
        if not موارد_انتخابی:
            QMessageBox.warning(self, "خطا", "لطفاً یک فایل را انتخاب کنید")
            return

        مسیر_ذخیره = QFileDialog.getExistingDirectory(
            self,
            "انتخاب مسیر ذخیره",
            self.تنظیمات['پوشه_نظارت']
        )
        
        if not مسیر_ذخیره:
            return

        try:
            s3 = self.دریافت_کلاینت_s3()
            if not s3:
                QMessageBox.warning(self, "خطا", "اتصال به سرور برقرار نشد")
                return

            for مورد in موارد_انتخابی:
                نام_فایل = مورد.text()
                مسیر_محلی = os.path.join(مسیر_ذخیره, نام_فایل)
                
                # دانلود فایل
                s3.download_file(
                    self.تنظیمات['نام_سطل'],
                    نام_فایل,
                    مسیر_محلی
                )
                
                # بررسی اینکه آیا فایل رمزنگاری شده است
                متادیتا = s3.head_object(
                    Bucket=self.تنظیمات['نام_سطل'],
                    Key=نام_فایل
                ).get('Metadata', {})
                
                if متادیتا.get('رمزنگاری', 'خیر') == 'بله':
                    self.رمزگشایی_فایل(مسیر_محلی)
                
                if متادیتا.get('فشرده', 'خیر') == 'بله' and نام_فایل.endswith('.zip'):
                    self.خارج_کردن_از_حالت_فشرده(مسیر_محلی)
                
                self.logger.info(f"فایل {نام_فایل} با موفقیت دانلود شد")
            
            QMessageBox.information(self, "موفقیت", "دانلود فایل‌ها با موفقیت انجام شد")
        except Exception as e:
            self.logger.error(f"خطا در دانلود فایل: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "خطا", f"خطا در دانلود فایل: {str(e)}")

    def رمزگشایی_فایل(self, مسیر_فایل):
        try:
            فرنت = Fernet(self.تنظیمات['کلید_فرنت'])
            with open(مسیر_فایل, 'rb') as فایل:
                داده_رمزنگاری = فایل.read()
            
            داده_رمزگشایی = فرنت.decrypt(داده_رمزنگاری)
            
            مسیر_رمزگشایی = مسیر_فایل[:-4] if مسیر_فایل.endswith('.enc') else مسیر_فایل + '.dec'
            with open(مسیر_رمزگشایی, 'wb') as فایل:
                فایل.write(داده_رمزگشایی)
            
            os.remove(مسیر_فایل)
            self.logger.info(f"فایل {مسیر_فایل} با موفقیت رمزگشایی شد")
            return مسیر_رمزگشایی
        except Exception as e:
            self.logger.error(f"خطا در رمزگشایی فایل: {str(e)}", exc_info=True)
            raise

    def خارج_کردن_از_حالت_فشرده(self, مسیر_زیپ):
        try:
            پوشه_مقصد = os.path.dirname(مسیر_زیپ)
            with zipfile.ZipFile(مسیر_زیپ, 'r') as زیپ:
                زیپ.extractall(پوشه_مقصد)
            
            os.remove(مسیر_زیپ)
            self.logger.info(f"فایل {مسیر_زیپ} با موفقیت از حالت فشرده خارج شد")
        except Exception as e:
            self.logger.error(f"خطا در خارج کردن از حالت فشرده: {str(e)}", exc_info=True)
            raise

    def حذف_فایل(self):
        موارد_انتخابی = self.لیست_فایل‌ها.selectedItems()
        if not موارد_انتخابی:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل یک فایل را انتخاب کنید")
            return

        پاسخ = QMessageBox.question(
            self,
            "تأیید حذف",
            f"آیا از حذف {len(موارد_انتخابی)} فایل انتخابی مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if پاسخ == QMessageBox.No:
            return

        try:
            s3 = self.دریافت_کلاینت_s3()
            if not s3:
                QMessageBox.warning(self, "خطا", "اتصال به سرور برقرار نشد")
                return

            for مورد in موارد_انتخابی:
                s3.delete_object(
                    Bucket=self.تنظیمات['نام_سطل'],
                    Key=مورد.text()
                )
                self.logger.info(f"فایل {مورد.text()} با موفقیت حذف شد")
            
            self.بروزرسانی_لیست_فایل‌ها()
            QMessageBox.information(self, "موفقیت", "فایل‌ها با موفقیت حذف شدند")
        except Exception as e:
            self.logger.error(f"خطا در حذف فایل: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "خطا", f"خطا در حذف فایل: {str(e)}")

    def تست_اتصال(self):
        try:
            s3 = self.دریافت_کلاینت_s3()
            if not s3:
                return False
            
            # انجام یک عملیات ساده برای تست اتصال
            s3.list_buckets()
            return True
        except:
            return False

    def تست_اتصال_ui(self):
        if self.تست_اتصال():
            QMessageBox.information(self, "موفقیت", "اتصال به سرور با موفقیت برقرار شد")
        else:
            QMessageBox.warning(self, "خطا", "اتصال به سرور برقرار نشد")

    def تغییر_پوشه_نظارت(self):
        مسیر_پوشه = QFileDialog.getExistingDirectory(
            self,
            "انتخاب دایرکتوری نظارت",
            self.تنظیمات['پوشه_نظارت']
        )
        
        if مسیر_پوشه:
            self.تنظیمات['پوشه_نظارت'] = مسیر_پوشه
            self.برچسب_پوشه_نظارت.setText(مسیر_پوشه)
            self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات)
            self.logger.info(f"دایرکتوری نظارت به {مسیر_پوشه} تغییر یافت")

    def تولید_کلید_جدید(self):
        پاسخ = QMessageBox.question(
            self,
            "تأیید تولید کلید جدید",
            "با تولید کلید جدید، تمام داده‌های رمزنگاری شده قبلی غیرقابل استفاده خواهند شد. آیا مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if پاسخ == QMessageBox.No:
            return

        کلید_جدید = Fernet.generate_key()
        self.تنظیمات['کلید_فرنت'] = کلید_جدید
        self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات)
        
        # ذخیره کلید در فایل
        with open('کلید_رمزنگاری.key', 'wb') as فایل:
            فایل.write(کلید_جدید)
        
        QMessageBox.information(self, "موفقیت", "کلید جدید با موفقیت تولید و ذخیره شد")
        self.logger.info("کلید رمزنگاری جدید تولید شد")

    def تست_اتصال_smtp(self):
        try:
            سرور = smtplib.SMTP(
                self.ورودی_سرور_smtp.text(),
                int(self.ورودی_پورت_smtp.text()))
            
            if self.چک_باکس_tls.isChecked():
                سرور.starttls()
            
            سرور.login(
                self.ورودی_کاربر_smtp.text(),
                self.ورودی_رمز_smtp.text()
            )
            
            سرور.quit()
            QMessageBox.information(self, "موفقیت", "اتصال SMTP با موفقیت برقرار شد")
            return True
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"اتصال SMTP برقرار نشد: {str(e)}")
            return False

    def ذخیره_تنظیمات(self):
        # ذخیره تنظیمات اتصال
        self.تنظیمات['آدرس_پایانه'] = self.ورودی_آدرس_پایانه.text()
        self.تنظیمات['نام_منطقه'] = self.ورودی_نام_منطقه.text()
        self.تنظیمات['کلید_دسترسی'] = self.ورودی_کلید_دسترسی.text()
        self.تنظیمات['کلید_مخفی'] = self.ورودی_کلید_مخفی.text()
        self.تنظیمات['نام_سطل'] = self.ورودی_نام_سطل.text()
        
        # ذخیره تنظیمات آپلود
        self.تنظیمات['فاصله_آپلود'] = self.اسپین_فاصله.value()
        self.تنظیمات['فشرده‌سازی_خودکار'] = self.کامبوباکس_فشرده‌سازی.currentIndex() == 0
        self.تنظیمات['نگهداری_کپی_محلی'] = self.کامبوباکس_کپی_محلی.currentIndex() == 0
        self.تنظیمات['حداکثر_پشتیبان'] = self.اسپین_حداکثر_پشتیبان.value()
        self.تنظیمات['رمزنگاری_فایل‌ها'] = self.کامبوباکس_رمزنگاری.currentIndex() == 0
        
        # ذخیره تنظیمات SMTP
        self.تنظیمات_smtp = {
            'سرور': self.ورودی_سرور_smtp.text(),
            'پورت': int(self.ورودی_پورت_smtp.text()),
            'نام_کاربری': self.ورودی_کاربر_smtp.text(),
            'رمز_عبور': self.ورودی_رمز_smtp.text(),
            'ایمیل_فرستنده': self.ورودی_فرستنده_smtp.text(),
            'فعال_سازی_tls': self.چک_باکس_tls.isChecked()
        }
        self.تنظیمات['تنظیمات_smtp'] = self.تنظیمات_smtp
        
        if self.ذخیره_داده_رمزنگاری(self.فایل_تنظیمات, self.تنظیمات):
            QMessageBox.information(self, "موفقیت", "تنظیمات با موفقیت ذخیره شد")
            self.logger.info("تنظیمات جدید ذخیره شد")
            
            # راه‌اندازی مجدد آپلود خودکار اگر فاصله تغییر کرده باشد
            if self.تایمر_آپلود_خودکار.isActive():
                self.تایمر_آپلود_خودکار.stop()
                self.تایمر_آپلود_خودکار.start(self.تنظیمات['فاصله_آپلود'] * 1000)
                self.برچسب_وضعیت.setText(f"وضعیت: فعال (هر {self.تنظیمات['فاصله_آپلود']} ثانیه)")

    def بروزرسانی_لیست_کاربران(self):
        self.لیست_کاربران.clear()
        for نام_کاربری, اطلاعات_کاربر in self.کاربران.items():
            نقش = اطلاعات_کاربر.get('نقش', 'کاربر')
            ایمیل = اطلاعات_کاربر.get('ایمیل', 'ثبت نشده')
            self.لیست_کاربران.addItem(f"{نام_کاربری} ({نقش}) - {ایمیل}")

    def افزودن_کاربر(self):
        دیالوگ = QDialog(self)
        دیالوگ.setWindowTitle("افزودن کاربر جدید")
        
        چیدمان = QVBoxLayout()
        فرم = QFormLayout()
        
        ورودی_نام = QLineEdit()
        ورودی_رمز = QLineEdit()
        ورودی_رمز.setEchoMode(QLineEdit.Password)
        ورودی_تکرار = QLineEdit()
        ورودی_تکرار.setEchoMode(QLineEdit.Password)
        ورودی_ایمیل = QLineEdit()
        کامبوباکس_نقش = QComboBox()
        کامبوباکس_نقش.addItems(["کاربر", "مدیر"])
        
        فرم.addRow("نام کاربری:", ورودی_نام)
        فرم.addRow("رمز عبور:", ورودی_رمز)
        فرم.addRow("تکرار رمز عبور:", ورودی_تکرار)
        فرم.addRow("ایمیل:", ورودی_ایمیل)
        فرم.addRow("نقش:", کامبوباکس_نقش)
        
        دکمه‌ها = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        دکمه‌ها.accepted.connect(lambda: self.ذخیره_کاربر_جدید(
            دیالوگ, ورودی_نام.text(), ورودی_رمز.text(), 
            ورودی_تکرار.text(), ورودی_ایمیل.text(), کامبوباکس_نقش.currentText()
        ))
        دکمه‌ها.rejected.connect(دیالوگ.reject)
        
        چیدمان.addLayout(فرم)
        چیدمان.addWidget(دکمه‌ها)
        دیالوگ.setLayout(چیدمان)
        دیالوگ.exec_()

    def ذخیره_کاربر_جدید(self, دیالوگ, نام_کاربری, رمز, تکرار, ایمیل, نقش):
        if not نام_کاربری or not رمز or not تکرار or not ایمیل:
            QMessageBox.warning(self, "خطا", "لطفاً تمام فیلدها را پر کنید")
            return
        
        if رمز != تکرار:
            QMessageBox.warning(self, "خطا", "رمزهای عبور مطابقت ندارند")
            return
        
        if نام_کاربری in self.کاربران:
            QMessageBox.warning(self, "خطا", "این نام کاربری قبلاً استفاده شده است")
            return
        
        self.کاربران[نام_کاربری] = {
            'رمز_عبور': self.هش_رمز(رمز),
            'نقش': نقش,
            'ایمیل': ایمیل,
            'توکن_بازیابی': None,
            'انقضای_توکن': None
        }
        
        self.ذخیره_داده_رمزنگاری(self.فایل_کاربران, self.کاربران)
        self.بروزرسانی_لیست_کاربران()
        دیالوگ.accept()
        self.logger.info(f"کاربر جدید اضافه شد: {نام_کاربری}")

    def ویرایش_کاربر(self):
        انتخاب = self.لیست_کاربران.currentItem()
        if not انتخاب:
            QMessageBox.warning(self, "خطا", "لطفاً یک کاربر را انتخاب کنید")
            return
        
        نام_کاربری = انتخاب.text().split(' ')[0]
        if نام_کاربری not in self.کاربران:
            return
        
        دیالوگ = QDialog(self)
        دیالوگ.setWindowTitle("ویرایش کاربر")
        
        چیدمان = QVBoxLayout()
        فرم = QFormLayout()
        
        ورودی_رمز = QLineEdit()
        ورودی_رمز.setPlaceholderText("خالی بگذارید برای عدم تغییر")
        ورودی_رمز.setEchoMode(QLineEdit.Password)
        ورودی_تکرار = QLineEdit()
        ورودی_تکرار.setEchoMode(QLine)
