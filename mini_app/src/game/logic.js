export function rollDice() {
  return [Math.ceil(Math.random() * 6), Math.ceil(Math.random() * 6)];
}

export function isDoubles(dice) {
  return dice[0] === dice[1];
}

export function countRailroads(cells, playerId) {
  return cells.filter(c => c.type === 'railroad' && c.owner === playerId).length;
}

export function countUtilities(cells, playerId) {
  return cells.filter(c => c.type === 'utility' && c.owner === playerId).length;
}

export function hasMonopoly(cells, playerId, colorGroup) {
  if (!colorGroup) return false;
  const group = cells.filter(c => c.colorGroup === colorGroup && c.type === 'street');
  return group.length > 0 && group.every(c => c.owner === playerId);
}

export function calculateRent(cell, cells, dice) {
  if (cell.owner == null) return 0;

  if (cell.type === 'railroad') {
    const n = countRailroads(cells, cell.owner);
    return cell.rent[n - 1] || 0;
  }

  if (cell.type === 'utility') {
    const n = countUtilities(cells, cell.owner);
    return (dice[0] + dice[1]) * (n === 2 ? 10 : 4);
  }

  if (cell.type === 'street') {
    if (cell.hotel) return cell.rent[5];
    if (cell.houses > 0) return cell.rent[cell.houses];
    if (hasMonopoly(cells, cell.owner, cell.colorGroup)) return cell.rent[0] * 2;
    return cell.rent[0];
  }

  return 0;
}

export function calculateRepairs(cells, playerId, hc, htc) {
  return cells
    .filter(c => c.owner === playerId)
    .reduce((sum, c) => {
      if (c.hotel) return sum + htc;
      if (c.houses) return sum + c.houses * hc;
      return sum;
    }, 0);
}

// ─── AI Decision ───────────────────────────────────────────
const BOT_THOUGHTS_WIN  = ['Всё идёт отлично 😎', 'Победа близко!', 'Мой план работает.'];
const BOT_THOUGHTS_LOSE = ['Надо нагнать!', 'Плохи дела, но ничего не потеряно.', 'Соберусь!'];
const BOT_THOUGHTS_IDLE = ['Ход сделан.', 'Жду своего шанса.', 'Тактика — терпение.'];

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

export function getAiDecision(gameState, botId) {
  const { cells, players } = gameState;
  const bot      = players.find(p => p.id === botId);
  const opponent = players.find(p => p.id !== botId);
  const curCell  = cells[bot.position];
  const thoughts = [];

  // ── Try to buy current cell ──
  if (
    curCell &&
    (curCell.type === 'street' || curCell.type === 'railroad' || curCell.type === 'utility') &&
    curCell.owner == null
  ) {
    const canAfford = bot.money >= curCell.price;
    const reserve   = bot.money - curCell.price;
    const oppOwns   = opponent.properties.some(p => {
      const c = cells[p]; return c && c.colorGroup === curCell.colorGroup;
    });

    if (canAfford && (reserve > 200 || curCell.type === 'railroad')) {
      thoughts.push(`Покупаю «${curCell.name}» за ${curCell.price}₽. Остаток: ${reserve}₽.`);
      return { action: 'buy', thoughts };
    } else if (canAfford && !oppOwns) {
      thoughts.push(`Беру «${curCell.name}» — у противника этой группы нет.`);
      return { action: 'buy', thoughts };
    } else if (!canAfford) {
      thoughts.push(`Хочу «${curCell.name}», но денег мало (${bot.money}₽).`);
    }
  }

  // ── Try to build houses ──
  const groupsOwned = [...new Set(
    cells.filter(c => c.owner === botId && c.type === 'street').map(c => c.colorGroup)
  )];

  for (const group of groupsOwned) {
    if (!hasMonopoly(cells, botId, group)) continue;
    const groupCells = cells.filter(c => c.colorGroup === group);
    const minH = Math.min(...groupCells.map(c => c.hotel ? 5 : (c.houses || 0)));
    const target = groupCells.find(c => {
      const h = c.hotel ? 5 : (c.houses || 0);
      return h === minH && !c.hotel && h < 5;
    });
    if (target && bot.money >= target.houseCost + 300) {
      const n = (target.houses || 0) + 1;
      const label = n === 5 ? 'отель' : `дом #${n}`;
      thoughts.push(`Строю ${label} на «${target.name}»! 🏠`);
      return { action: 'build', targetPos: target.pos, thoughts };
    }
  }

  // ── End turn comment ──
  if (bot.money > opponent.money) {
    thoughts.push(`У меня ${bot.money}₽, у оппонента ${opponent.money}₽. ${pick(BOT_THOUGHTS_WIN)}`);
  } else if (bot.money < opponent.money - 200) {
    thoughts.push(`У меня ${bot.money}₽, у оппонента ${opponent.money}₽. ${pick(BOT_THOUGHTS_LOSE)}`);
  } else {
    thoughts.push(pick(BOT_THOUGHTS_IDLE));
  }

  return { action: 'endTurn', thoughts };
}
