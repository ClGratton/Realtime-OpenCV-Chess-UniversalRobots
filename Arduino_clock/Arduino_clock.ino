#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <avr/io.h>
#include <util/delay.h>

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels



Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT);

int buttons[] = {2, 3, 3, 5, 6, 7}; // Create an array of button pin numbers
bool buttonValues[] = {false, false, false, false, false, false}; // Create an array for button states

int buzzerPin = 8;

typedef enum {
  start,
  white_time,
  white_increment,
  black_time,
  black_increment,
  white_move,
  black_move,
  finish
} State;

State states;

typedef struct {
  int hours;
  int minutes;
  int seconds;
} Time;

typedef struct {
  int minutes;
  int seconds;
} Increment;


Time time_white = {00, 00, 00};
Increment increment_white = {00, 00};
Time time_black = {00, 00, 00};
Increment increment_black = {00, 00};
int millis1;
int millis2;
bool black_button = HIGH;

bool PassState;


/*void printToScreen() {
  display.clearDisplay();
  display.setTextColor( WHITE);
  display.setTextSize(1);
  display.setCursor(3, 3);
  display.println("Black");
  display.setTextSize(3);
  display.setCursor(0, (SCREEN_HEIGHT / 2) - 8);
  display.println("Ready?");
  display.display();
  }*/


void updateButtons() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    buttonValues[i] = digitalRead(buttons[i]);  // Read initial button state
  }
}


void setup() {
  for (int i = 0; i < sizeof(buttons) / sizeof(buttons[0]); i++) {
    pinMode(buttons[i], INPUT_PULLUP);
    buttonValues[i] = digitalRead(buttons[i]); // Read initial button state
  }

  Serial.begin(9600);

  pinMode(buzzerPin, OUTPUT);


  if (!display.begin( SSD1306_SWITCHCAPVCC, 0x3C)) {
    while (true);

  }
  display.clearDisplay();
  display.display();

  states = start;
}


void loop() {

  updateButtons();
  buzzer();
  Serial.println(states);

  switch (states) {

    case start:

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_time;
      }


      break;


    case white_time:

      if (buttonValues[0] == LOW)  {
        if (!(time_white.seconds == 0 && time_white.minutes == 0 && time_white.hours == 0)) {
          time_white.seconds =  time_white.seconds - 30;

          if ((time_white.seconds < 0)) {
            time_white.seconds = 30;
            time_white.minutes--;
          }

          if (time_white.minutes < 0 && time_white.hours != 0) {
            time_white.seconds = 30;
            time_white.minutes = 59;
            time_white.hours--;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        time_white.seconds =  time_white.seconds + 30;
        if (time_white.seconds >  59) {
          time_white.seconds = 0;
          time_white.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (time_white.minutes > 59 ) {
          time_white.seconds = 0;
          time_white.minutes = 0;
          time_white.hours++;
        }
      }

      printWhiteTime();


      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_increment;
      }

      delay(120);

      break;

    case white_increment:
      if (buttonValues[0] == LOW)  {
        if (!(increment_white.seconds == 0 && increment_white.minutes == 0)) {
          increment_white.seconds =  increment_white.seconds - 1;

          if ((increment_white.seconds < 0)) {
            increment_white.seconds = 59;
            increment_white.minutes--;
          }

          if (increment_white.minutes < 0 ) {
            increment_white.seconds = 59;
            increment_white.minutes = 59;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        increment_white.seconds =  increment_white.seconds + 1;
        if (increment_white.seconds >  59) {
          increment_white.seconds = 0;
          increment_white.minutes++;
        }

        // If minutes are also zero, decrement hours
        if (increment_white.minutes > 59 ) {
          increment_white.seconds = 0;
          increment_white.minutes = 0;
        }
      }

      display.clearDisplay();
      display.setTextColor( WHITE);
      display.setTextSize(2);
      display.setCursor(2, 0);
      display.print("Increment:");
      //display.print(String(time_white.hours) + ":" + String(time_white.minutes) + ":" + String(time_white.seconds))

      if (increment_white.minutes < 10) {
        display.setCursor(2, (SCREEN_HEIGHT / 2) );
        display.print('0');
        display.print(increment_white.minutes);
        display.print(':');
      } else {
        display.print(increment_white.minutes);
        display.print(':');
      }

      if (increment_white.seconds < 10) {
        display.setCursor(37, (SCREEN_HEIGHT / 2) );
        display.print('0');
        display.print(increment_white.seconds);
      } else {
        display.print(increment_white.seconds);
      };
      display.display();

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = black_time;
      }



      delay(120);

      break;

    case black_time:

      printWhiteTime();

      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = black_increment;

        
        }
      }

      delay(120);
      break;

    case black_increment:
      if (buttonValues[3] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[3] == HIGH) {
        PassState = LOW;
        states = white_move;

        
        time_white.seconds = time_white.seconds + increment_white.seconds;
        time_white.minutes = time_white.minutes + increment_white.minutes;

        // Check for seconds overflow
        if (time_white.seconds >= 60) {
          time_white.seconds -= 60;
          time_white.minutes ++;
        }

        // Check for minutes overflow
        if (time_white.minutes >= 60) {
          time_white.minutes -= 60;
          time_white.hours++;
      }

      break;

    case white_move:

      printWhiteTime();


      if (black_button) {
        millis1 = millis();
        black_button = LOW;
      }

      if ((int(millis()) - millis1) > 1000) {
        time_white.seconds --;
        millis1 = 0;
        black_button = HIGH;

        if (time_white.seconds <= 0 && time_white.minutes <= 0 && time_white.hours <= 0) {
          states = finish;
        }

        if ((time_white.seconds < 0)) {
          time_white.seconds = 59;
          time_white.minutes--;
        }

        if (time_white.minutes < 0 && time_white.hours != 0) {
          time_white.seconds = 59;
          time_white.minutes = 59;
          time_white.hours--;
        }
      }

      if (buttonValues[4] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[4] == HIGH) {
        PassState = LOW;
        states = black_move;

        time_white.seconds = time_white.seconds + increment_white.seconds;
        time_white.minutes = time_white.minutes + increment_white.minutes;

        // Check for seconds overflow
        if (time_white.seconds >= 60) {
          time_white.seconds -= 60;
          time_white.minutes ++;
        }

        // Check for minutes overflow
        if (time_white.minutes >= 60) {
          time_white.minutes -= 60;
          time_white.hours++;
      }



      break;

    case black_move:

      if (buttonValues[5] == LOW)  {
        PassState = HIGH;
      }

      if (PassState && buttonValues[5] == HIGH) {
        PassState = LOW;
        states = white_move;

        time_black.seconds = time_black.seconds + increment_black.seconds;
        time_black.minutes = time_black.minutes + increment_black.minutes;

        // Check for seconds overflow
        if (time_black.seconds >= 60) {
          time_black.seconds -= 60;
          time_black.minutes ++;
        }

        // Check for minutes overflow
        if (time_black.minutes >= 60) {
          time_black.minutes -= 60;
          time_black.hours++;
      }
      break;

    case finish:
      printWhiteTime();
      break;
  }
}
