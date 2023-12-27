#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT);

int buttons[] = {2, 3, 3, 5, 6, 7}; // Create an array of button pin numbers
bool buttonValues[] = {false, false, false, false, false, false}; // Create an array for button states

typedef enum {
  stopt,
  white_time,
  white_increment,
  black_time,
  white_move,
  black_move,
  // ... other states
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
unsigned long previousMillis = 0;
unsigned int interval = 1000; // Interval for time updates in milliseconds


void printToScreen() {
  display.clearDisplay();
  display.setTextColor( WHITE);
  display.setTextSize(1);
  display.setCursor(3, 3);
  display.println("Black");
  display.setTextSize(3);
  display.setCursor(0, (SCREEN_HEIGHT / 2) - 8);
  display.println("Ready?");
  display.display();
}


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


  if (!display.begin( SSD1306_SWITCHCAPVCC, 0x3C)) {
    while (true);

  }
  display.clearDisplay();
  display.display();

  states = stopt;
}

void loop() {

  updateButtons();
  Serial.println(buttonValues[0]);

  switch (states) {

    case stopt:

      if (buttonValues[3] == LOW)  {
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


      display.clearDisplay();
      display.setTextColor( WHITE);
      display.setTextSize(2);
      //display.print(String(time_white.hours) + ":" + String(time_white.minutes) + ":" + String(time_white.seconds))
      if (time_white.hours < 10) {
        display.setCursor(0, (SCREEN_HEIGHT / 2) - 8);
        display.print('0');
        display.print(time_white.hours);
        display.print(':');
      } else {
        display.print(time_white.hours);
        display.print(':');
      }

      if (time_white.minutes < 10) {
        display.setCursor(35, (SCREEN_HEIGHT / 2) - 8);
        display.print('0');
        display.print(time_white.minutes);
        display.print(':');
      } else {
        display.print(time_white.minutes);
        display.print(':');
      }

      if (time_white.seconds < 10) {
        display.setCursor(70, (SCREEN_HEIGHT / 2) - 8);
        display.print('0');
        display.print(time_white.seconds);
      } else {
        display.print(time_white.seconds);
      };
      display.display();


      if (buttonValues[3] == LOW)  {
        states = white_increment;
      }

      delay(180);

      break;

    case white_increment:
      if (buttonValues[0] == LOW)  {
        if (!(increment_white.seconds == 0 && increment_white.minutes == 0)) {
          increment_white.seconds =  increment_white.seconds - 30;

          if ((increment_white.seconds < 0)) {
            increment_white.seconds = 30;
            increment_white.minutes--;
          }

          if (increment_white.minutes < 0 ) {
            increment_white.seconds = 30;
            increment_white.minutes = 59;
          }
        }
      }

      if (buttonValues[1] == LOW)  {
        increment_white.seconds =  increment_white.seconds + 30;
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
      //display.print(String(time_white.hours) + ":" + String(time_white.minutes) + ":" + String(time_white.seconds))

      if (increment_white.minutes < 10) {
        display.setCursor(35, (SCREEN_HEIGHT / 2) - 8);
        display.print('0');
        display.print(increment_white.minutes);
        display.print(':');
      } else {
        display.print(increment_white.minutes);
        display.print(':');
      }

      if (increment_white.seconds < 10) {
        display.setCursor(70, (SCREEN_HEIGHT / 2) - 8);
        display.print('0');
        display.print(increment_white.seconds);
      } else {
        display.print(increment_white.seconds);
      };
      display.display();


      if (buttonValues[3] == LOW)  {
        states = black_time;
      }

      delay(180);

      break;

    case black_time:

      break;

    case white_move:

      if (time_white.seconds > 0) {
        time_white.seconds--;
      } else {
        // If seconds are zero, decrement minutes
        if (time_white.minutes > 0) {
          time_white.seconds = 59;
          time_white.minutes--;
        } else {
          // If minutes are also zero, decrement hours
          if (time_white.hours > 0) {
            time_white.seconds = 59;
            time_white.minutes = 59;
            time_white.hours--;
          } else {
            // If hours are zero, stopwatch has reached zero
            Serial.println("Stopwatch has reached zero");
            while (true);
          }
        }
      }

      break;

    case black_move:

      break;
  }

}
