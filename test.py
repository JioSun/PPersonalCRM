from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, selectinload

Base = declarative_base()


# --- 1. ОПИСАНИЕ МОДЕЛЕЙ (БЕЗ FOREIGN KEY) ---

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    description = Column(String)

    # Настраиваем связь без физического FK в базе данных
    statuses = relationship(
        "OrderStatus",
        primaryjoin="Order.id == OrderStatus.order_id",
        foreign_keys="[OrderStatus.order_id]"
    )


class OrderStatus(Base):
    __tablename__ = 'order_status'
    id = Column(Integer, primary_key=True)
    # Обрати внимание: это просто Integer, без ForeignKey('orders.id')
    order_id = Column(Integer)
    status_name = Column(String)


# --- 2. НАСТРОЙКА БАЗЫ ДАННЫХ ---
# echo=True включит логирование всех SQL-запросов в консоль
engine = create_engine('sqlite:///:memory:', echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def run_test():
    with Session() as session:

        # --- 3. ЗАПОЛНЕНИЕ ДАННЫМИ ---
        print("\n" + "=" * 50)
        print("СОЗДАЕМ ДАННЫЕ (заказы и их статусы)")
        print("=" * 50)

        # Создаем 2 заказа
        order1 = Order(description="Заказ №1 (Ноутбук)")
        order2 = Order(description="Заказ №2 (Мышка)")
        session.add_all([order1, order2])
        session.commit()  # Сохраняем, чтобы получить их ID

        # Накидываем историю статусов для заказов
        statuses = [
            OrderStatus(order_id=order1.id, status_name="Ожидает оплаты"),
            OrderStatus(order_id=order1.id, status_name="Оплачен"),
            OrderStatus(order_id=order1.id, status_name="Передан курьеру"),
            OrderStatus(order_id=order2.id, status_name="Ожидает оплаты"),
            OrderStatus(order_id=order2.id, status_name="Отменен"),
        ]
        session.add_all(statuses)
        session.commit()

        # --- 4. ТЕСТИРОВАНИЕ SELECTINLOAD ---
        print("\n" + "=" * 50)
        print("ВЫПОЛНЯЕМ ЗАПРОС С SELECTINLOAD")
        print("Смотри на SQL-логи ниже!")
        print("=" * 50 + "\n")

        # Тот самый запрос, который делает магию в 2 этапа
        orders = session.query(Order).options(selectinload(Order.statuses)).all()

        # --- 5. ВЫВОД РЕЗУЛЬТАТА В PYTHON ---
        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТ СБОРКИ В PYTHON:")
        print("=" * 50)

        for order in orders:
            print(f"📦 {order.description} (ID: {order.id})")
            for status in order.statuses:
                print(f"   ↳ {status.status_name}")
            print("-" * 30)


if __name__ == "__main__":
    run_test()