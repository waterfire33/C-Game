#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <SFML/Graphics.hpp>

class MainWindow
{
public:
    MainWindow( int width, int height, const char* title );
    ~MainWindow();
    bool IsOpen() const;
    void Close();
    sf::RenderWindow& GetWindow();
    
private:
    sf::RenderWindow window;
};

#endif
