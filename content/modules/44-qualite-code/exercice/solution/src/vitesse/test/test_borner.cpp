// Copyright 2026 Umoja Roboti
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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
