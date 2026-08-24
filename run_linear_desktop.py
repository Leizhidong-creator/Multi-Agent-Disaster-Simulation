from app.desktop.main_window import ZhiyanMainWindow, create_application


def main() -> None:
    app = create_application()
    window = ZhiyanMainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
