"""
app/budget/exceptions.py — Budget Guard özel istisna sınıfları.

Bu istisnalar herhangi bir LLM çağrısının yarıda kesilmesi gerektiğinde
fırlatılır. Celery task'ları bu istisnaları yakalayarak retry yapmak
YERINE görevi FAILED olarak işaretlemelidir — para harcanmasını önler.
"""


class BudgetGuardError(Exception):
    """
    Budget Guard'ın kendisi beklenmedik bir hatayla çöktüğünde fırlatılır.
    
    Tasarım ilkesi — FAIL CLOSED:
        Guard'ın kendisi çökerse, API çağrısına izin VERME.
        Belirsizlik durumunda her zaman daha güvenli tarafı seç.
    """
    pass


class BudgetExceededError(BudgetGuardError):
    """
    Günlük bütçe limiti aşıldığında veya aşılacağı tahmin edildiğinde fırlatılır.
    Circuit Breaker bu istisna üzerine OPEN konumuna geçer.
    
    Celery task'larında bu istisna RETRY edilmemelidir:
        except BudgetExceededError:
            raise  # Celery'nin kendi retry mekanizmasına bırakma!
    """
    def __init__(self, message: str, spent_usd: float = 0.0, limit_usd: float = 0.0):
        super().__init__(message)
        self.spent_usd = spent_usd
        self.limit_usd = limit_usd


class CircuitBreakerOpenError(BudgetGuardError):
    """
    Circuit Breaker OPEN konumundayken herhangi bir API çağrısı
    yapılmaya çalışıldığında fırlatılır.
    
    OPEN konumu, gece yarısı Celery Beat tarafından otomatik olarak
    sıfırlanır. Elle sıfırlamak için /api/budget/reset kullanılır.
    """
    pass


class InsufficientBudgetError(BudgetExceededError):
    """
    Pre-flight check sırasında tahmini maliyet + mevcut harcama,
    bütçe limitini aşacaksa fırlatılır.
    
    Limit henüz aşılmamıştır ama bu görev için yeterli bütçe yoktur.
    """
    def __init__(self, message: str, est_cost: float = 0.0, remaining: float = 0.0):
        super().__init__(message)
        self.est_cost = est_cost
        self.remaining = remaining
