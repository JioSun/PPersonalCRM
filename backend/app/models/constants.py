from enum import Enum

class DealStatus(str, Enum):
    NEW = "new"                # заявка/договорённость получена, работа не начата
    IN_PROGRESS = "in_progress" # работа идёт
    ON_REVIEW = "on_review"    # отдано клиенту на проверку/правки
    COMPLETED = "completed"    # принято клиентом, работа сдана
    CANCELLED = "cancelled"