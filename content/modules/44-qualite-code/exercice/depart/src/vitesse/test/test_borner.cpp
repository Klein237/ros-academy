#include <gtest/gtest.h>

#include "vitesse/borner.hpp"

TEST(TestBorner, SousLaLimite)
{
  EXPECT_DOUBLE_EQ(vitesse::borner(0.2, 0.5), 0.2);
}

TEST(TestBorner, MarcheAvant)
{
  EXPECT_DOUBLE_EQ(vitesse::borner(2.0, 0.5), 0.5);
}

TEST(TestBorner, MarcheArriere)
{
  EXPECT_DOUBLE_EQ(vitesse::borner(-2.0, 0.5), -0.5);
}
