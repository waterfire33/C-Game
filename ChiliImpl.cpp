#include "Mainwindow.h"
#include "Game.h"
#include "Graphics.h"

// Mainwindow Implementation
MainWindow::MainWindow( int width, int height, const char* title )
    : window( sf::VideoMode( {static_cast<unsigned int>(width), static_cast<unsigned int>(height)} ), title )
{
}

MainWindow::~MainWindow()
{
}

bool MainWindow::IsOpen() const
{
    return window.isOpen();
}

void MainWindow::Close()
{
    window.close();
}

sf::RenderWindow& MainWindow::GetWindow()
{
    return window;
}

// Graphics Implementation
Graphics::Graphics( MainWindow& wnd )
    : wnd( wnd ),
      window( wnd.GetWindow() )
{
}

Graphics::~Graphics()
{
}

void Graphics::BeginFrame()
{
    window.clear( sf::Color::Black );
}

void Graphics::EndFrame()
{
    window.display();
}

void Graphics::PutPixel( int x, int y, int r, int g, int b )
{
    sf::RectangleShape pixel( {1.0f, 1.0f} );
    pixel.setPosition( {static_cast<float>(x), static_cast<float>(y)} );
    pixel.setFillColor( sf::Color( r, g, b ) );
    window.draw( pixel );
}

// Game Implementation
Game::Game( MainWindow& wnd )
    : wnd( wnd ),
      gfx( wnd )
{
}

Game::~Game()
{
}

void Game::Go()
{
    gfx.BeginFrame();
    UpdateModel();
    ComposeFrame();
    gfx.EndFrame();
}

void Game::UpdateModel()
{
}

void Game::ComposeFrame()
{
    gfx.PutPixel( 100, 100, 255, 255, 255 );
}
