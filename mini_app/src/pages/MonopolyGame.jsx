import { useReducer, useEffect, useCallback, useRef, useState } from 'react';
import { BOARD_CELLS, CELL_GRID, CELL_SIDE, COLOR_MAP } from '../game/boardData';
import { CHANCE_CARDS, COMMUNITY_CARDS } from '../game/cards';
import {
  rollDice, isDoubles, calculateRent, calculateRepairs,
  hasMonopoly, getAiDecision,
} from '../game/logic';
import api from '../api';

// ─── Initial state ─────────────────────────────────────────
const initCells = () => BOARD_CELLS.map(c => ({
  ...c, owner: null, houses: 0, hotel: false,
}));

const initPlayers = (userName) => [
  { id:0, name: userName || 'Игрок', money:1500, position:0, properties:[], inJail:false, jailTurns:0, doublesRow:0, bankrupt:false, jailFreeCard:false },
  { id:1, name:'Бот 🤖',             money:1500, position:0, properties:[], inJail:false, jailTurns:0, doublesRow:0, bankrupt:false, jailFreeCard:false },
];

const INITIAL_STATE = (userName) => ({
  cells:    initCells(),
  players:  initPlayers(userName),
  current:  0,        // 0 = human, 1 = bot
  phase:    'roll',   // roll | action | card | gameover
  dice:     [1,1],
  diceAnim: false,
  log:      ['🎮 Игра началась! Бросьте кубики.'],
  card:     null,     // { text, action }
  winner:   null,
});

// ─── Reducer ───────────────────────────────────────────────
function reducer(state, act) {
  switch (act.type) {

    case 'RESET': return INITIAL_STATE(act.userName);

    case '_LOG': return { ...state, log: addLog(state.log, act.msg) };

    case 'DICE_ANIM': return { ...state, diceAnim: act.v };

    case 'ROLL': {
      const dice    = act.dice;
      const { current, players, cells } = state;
      const player  = players[current];
      const doubles = isDoubles(dice);

      if (player.inJail) {
        if (doubles) {
          const np = { ...player, inJail:false, jailTurns:0, doublesRow:0 };
          const newPos = (player.position + dice[0] + dice[1]) % 40;
          return landOn(
            { ...state, dice, players: swap(players, current, np), log: addLog(state.log, `${player.name} выбросил дубль — вышел из тюрьмы!`) },
            current, newPos
          );
        }
        const jailTurns = player.jailTurns + 1;
        if (jailTurns >= 3) {
          // Must pay
          const np = { ...player, money: player.money - 50, inJail:false, jailTurns:0 };
          const newPos = (player.position + dice[0] + dice[1]) % 40;
          return landOn(
            { ...state, dice, players: swap(players, current, np), log: addLog(state.log, `${player.name} заплатил 50₽ за выход из тюрьмы.`) },
            current, newPos
          );
        }
        return {
          ...state, dice,
          players: swap(players, current, { ...player, jailTurns }),
          phase:   'action',
          log: addLog(state.log, `${player.name} в тюрьме (ход ${jailTurns}/3). Нет дубля.`),
        };
      }

      const doublesRow = doubles ? player.doublesRow + 1 : 0;
      if (doublesRow >= 3) {
        // Three doubles in a row → jail
        const np = { ...player, inJail:true, position:10, jailTurns:0, doublesRow:0 };
        return {
          ...state, dice,
          players: swap(players, current, np),
          phase:   'action',
          log: addLog(state.log, `${player.name} бросил трёхкратный дубль — тюрьма! 👮`),
        };
      }

      const steps  = dice[0] + dice[1];
      const oldPos = player.position;
      const newPos = (oldPos + steps) % 40;
      const passGo = oldPos + steps >= 40 && !player.inJail;

      let np = { ...player, doublesRow };
      if (passGo) {
        np = { ...np, money: np.money + 200 };
      }

      const s = passGo
        ? addLog(state.log, `${player.name} прошёл Старт — +200₽!`)
        : state.log;

      return landOn({ ...state, dice, players: swap(players, current, np), log: s }, current, newPos);
    }

    case 'BUY': {
      const { current, players, cells } = state;
      const player = players[current];
      const cell   = cells[player.position];
      if (!cell || cell.owner != null || player.money < cell.price) return state;

      const np = { ...player, money: player.money - cell.price, properties: [...player.properties, cell.pos] };
      const nc = cells.map(c => c.pos === cell.pos ? { ...c, owner: current } : c);
      return {
        ...state,
        cells: nc,
        players: swap(players, current, np),
        phase: 'action',
        log: addLog(state.log, `${player.name} купил «${cell.name}» за ${cell.price}₽.`),
      };
    }

    case 'SKIP_BUY': return { ...state, phase: 'action' };

    case 'BUILD': {
      const { current, players, cells } = state;
      const player = players[current];
      const cell   = cells[act.pos];
      if (!cell || cell.owner !== current) return state;
      if (cell.hotel) return state;
      const cost = cell.houseCost;
      if (player.money < cost) return state;

      const np = { ...player, money: player.money - cost };
      const nc = cells.map(c => {
        if (c.pos !== act.pos) return c;
        if (c.houses >= 4) return { ...c, houses:0, hotel:true };
        return { ...c, houses: c.houses + 1 };
      });
      const label = (cell.houses >= 4) ? 'отель' : `дом #${cell.houses + 1}`;
      return {
        ...state,
        cells: nc,
        players: swap(players, current, np),
        log: addLog(state.log, `${player.name} построил ${label} на «${cell.name}» (-${cost}₽).`),
      };
    }

    case 'END_TURN': {
      const { current, players, dice } = state;
      const player   = players[current];
      const doubles  = isDoubles(dice);
      const wasInJail = player.inJail;

      if (doubles && !wasInJail && player.doublesRow > 0 && player.doublesRow < 3) {
        // Extra turn for doubles
        return { ...state, phase:'roll', log: addLog(state.log, `${player.name} снова ходит (дубль!)`) };
      }

      const next = current === 0 ? 1 : 0;
      if (players[next].bankrupt) return { ...state, phase:'roll', current: next };
      return {
        ...state,
        current: next,
        phase: 'roll',
        log: addLog(state.log, `Ход переходит к: ${players[next].name}`),
      };
    }

    case 'DISMISS_CARD': {
      const { card, current, players, cells } = state;
      if (!card) return { ...state, phase:'action' };
      const { action } = card;
      let s = { ...state, card: null };

      const player = players[current];

      if (action.type === 'collect') {
        const np = { ...player, money: player.money + action.amount };
        s = { ...s, players: swap(players, current, np), log: addLog(s.log, `+${action.amount}₽`) };
      } else if (action.type === 'pay') {
        const np = { ...player, money: player.money - action.amount };
        s = checkBankrupt({ ...s, players: swap(players, current, np), log: addLog(s.log, `-${action.amount}₽`) }, current);
      } else if (action.type === 'goto') {
        const collect = action.collect && action.pos <= player.position ? action.collect : 0;
        let np = { ...player, money: player.money + collect };
        if (collect) s = { ...s, log: addLog(s.log, `+${collect}₽ за проход Старта`) };
        s = landOn({ ...s, players: swap(s.players, current, np) }, current, action.pos);
        return s;
      } else if (action.type === 'jail') {
        const np = { ...player, position:10, inJail:true, jailTurns:0, doublesRow:0 };
        s = { ...s, players: swap(players, current, np), phase:'action', log: addLog(s.log, `${player.name} идёт в тюрьму.`) };
      } else if (action.type === 'jailFree') {
        const np = { ...player, jailFreeCard:true };
        s = { ...s, players: swap(players, current, np), log: addLog(s.log, `${player.name} получил карточку выхода из тюрьмы.`) };
      } else if (action.type === 'back') {
        const newPos = ((player.position - action.amount) + 40) % 40;
        s = landOn(s, current, newPos);
        return s;
      } else if (action.type === 'birthday') {
        const opponent = players.find(p => p.id !== current);
        const np = { ...player, money: player.money + action.amount };
        const no = { ...opponent, money: opponent.money - action.amount };
        s = { ...s, players: swap(swap(players, current, np), opponent.id, no), log: addLog(s.log, `${player.name} собрал ${action.amount}₽ с оппонента.`) };
      } else if (action.type === 'repairs') {
        const cost = calculateRepairs(cells, current, action.house, action.hotel);
        const np = { ...player, money: player.money - cost };
        s = checkBankrupt({ ...s, players: swap(players, current, np), log: addLog(s.log, `Ремонт: -${cost}₽`) }, current);
      }

      return { ...s, phase:'action' };
    }

    case 'PAY_JAIL': {
      const { current, players } = state;
      const player = players[current];
      if (player.money < 50) return state;
      const np = { ...player, money: player.money - 50, inJail:false, jailTurns:0 };
      return {
        ...state,
        players: swap(players, current, np),
        log: addLog(state.log, `${player.name} заплатил 50₽ и вышел из тюрьмы.`),
      };
    }

    case 'SYNC_STATE': return { ...act.state };

    default: return state;
  }
}

// ─── Helpers ───────────────────────────────────────────────
function swap(arr, idx, val) {
  return arr.map((x, i) => i === idx ? val : x);
}

function addLog(log, msg) {
  return [...log.slice(-49), msg];
}

function landOn(state, playerId, newPos) {
  const { cells, players, dice } = state;
  const player  = players[playerId];
  const np      = { ...player, position: newPos };
  let s         = { ...state, players: swap(players, playerId, np) };
  const cell    = cells[newPos];

  if (!cell) return { ...s, phase: 'action' };

  // Special cells
  if (cell.type === 'goToJail') {
    const jailedP = { ...np, inJail:true, position:10, jailTurns:0, doublesRow:0 };
    return { ...s, players: swap(s.players, playerId, jailedP), phase:'action', log: addLog(s.log, `${player.name} → В тюрьму! 👮`) };
  }

  if (cell.type === 'go' || cell.type === 'jail' || cell.type === 'parking') {
    return { ...s, phase:'action', log: addLog(s.log, `${player.name} на «${cell.name}»`) };
  }

  if (cell.type === 'tax') {
    const cost = cell.tax || 0;
    const taxedP = { ...np, money: np.money - cost };
    s = checkBankrupt({ ...s, players: swap(s.players, playerId, taxedP), log: addLog(s.log, `${player.name} заплатил налог ${cost}₽`) }, playerId);
    return { ...s, phase:'action' };
  }

  if (cell.type === 'chance' || cell.type === 'community') {
    const deck = cell.type === 'chance' ? CHANCE_CARDS : COMMUNITY_CARDS;
    const card = deck[Math.floor(Math.random() * deck.length)];
    return { ...s, phase:'card', card, log: addLog(s.log, `${player.name} тянет карту ${cell.type === 'chance' ? '❓ Шанс' : '📦 Казна'}`) };
  }

  // Street / railroad / utility
  if (cell.owner == null) {
    // Unowned — offer to buy
    return { ...s, phase:'buy', log: addLog(s.log, `${player.name} на «${cell.name}» (${cell.price}₽)`) };
  }

  if (cell.owner === playerId) {
    return { ...s, phase:'action', log: addLog(s.log, `${player.name} на своей «${cell.name}»`) };
  }

  // Owned by opponent → pay rent
  const rent = calculateRent(cell, cells, dice);
  const opponent = s.players.find(p => p.id !== playerId);
  const paidP = { ...np, money: np.money - rent };
  const richP = { ...opponent, money: opponent.money + rent };
  s = { ...s, players: swap(swap(s.players, playerId, paidP), opponent.id, richP), log: addLog(s.log, `${player.name} платит ${rent}₽ аренды за «${cell.name}»`) };
  s = checkBankrupt(s, playerId);
  return { ...s, phase:'action' };
}

function checkBankrupt(state, playerId) {
  const player = state.players[playerId];
  if (player.money >= 0) return state;

  // Simplified: if money < 0 → bankrupt
  const np = { ...player, bankrupt:true, money:0 };
  const opponent = state.players.find(p => p.id !== playerId);
  return {
    ...state,
    players: swap(state.players, playerId, np),
    phase:   'gameover',
    winner:  opponent.id,
    log: addLog(state.log, `💥 ${player.name} банкрот! ${opponent.name} победил!`),
  };
}

// ─── Board Cell Component ──────────────────────────────────
// color band position: bottom→top of cell, top→bottom, left→right, right→left (all toward center)
function BoardCell({ cell, side, tokens, isCorner }) {
  const bandColor = cell.colorGroup ? COLOR_MAP[cell.colorGroup] : null;
  const showBand  = !!bandColor && !isCorner;

  return (
    <div style={{ gridColumn: CELL_GRID[cell.pos][0], gridRow: CELL_GRID[cell.pos][1] }}>
      <div className={`mcell mcell-${side}${isCorner ? ' mcell-corner' : ''}`}>

        {/* Color band — always toward board center */}
        {showBand && (
          <div className={`mcell-band mcell-band-${side}`}
               style={{ background: bandColor }} />
        )}

        {/* Content — always horizontal, readable */}
        <div className="mcell-body">
          {cell.icon && <span className="mcell-icon">{cell.icon}</span>}
          <span className="mcell-name">{cell.name}</span>
          {cell.price > 0 && <span className="mcell-price">{cell.price}₽</span>}
          {(cell.hotel || cell.houses > 0) && (
            <span className="mcell-houses">
              {cell.hotel ? '🏨' : '🏠'.repeat(cell.houses)}
            </span>
          )}
        </div>

        {/* Player tokens */}
        <div className="mcell-tokens">
          {tokens.map(t => (
            <div key={t.id} className="mtoken" style={{ background: t.color }}>{t.icon}</div>
          ))}
        </div>

        {/* Owner dot */}
        {cell.owner != null && (
          <div className="mcell-owner-dot"
               style={{ background: PLAYER_COLORS[cell.owner] }} />
        )}
      </div>
    </div>
  );
}

// ─── Dice Component ────────────────────────────────────────
const DICE_FACES = ['', '⚀','⚁','⚂','⚃','⚄','⚅'];

function Dice({ dice, rolling }) {
  return (
    <div className="mdice">
      <span className={`mdie${rolling ? ' mdie-roll' : ''}`}>{DICE_FACES[dice[0]]}</span>
      <span className={`mdie${rolling ? ' mdie-roll' : ''}`}>{DICE_FACES[dice[1]]}</span>
      <span className="mdice-sum">{dice[0] + dice[1]}</span>
    </div>
  );
}

// ─── Player Card ───────────────────────────────────────────
const PLAYER_COLORS = ['#e74c3c', '#3498db'];
const PLAYER_ICONS  = ['🔴', '🔵'];

function PlayerCard({ player, isActive, cells }) {
  const props = cells.filter(c => c.owner === player.id);
  return (
    <div className={`mplayer-card${isActive ? ' mplayer-active' : ''}`}>
      <div className="mplayer-header">
        <span style={{ fontSize:18 }}>{PLAYER_ICONS[player.id]}</span>
        <div>
          <div className="mplayer-name">{player.name}</div>
          <div className="mplayer-money">💰 {player.money}₽</div>
        </div>
        {player.inJail && <span className="mplayer-jail">🏛️</span>}
        {player.bankrupt && <span className="mplayer-bankrupt">💥</span>}
      </div>
      <div className="mplayer-props">
        {props.slice(0,6).map(c => (
          <span key={c.pos} className="mplayer-prop-dot"
            style={{ background: c.colorGroup ? COLOR_MAP[c.colorGroup] : '#888' }}
            title={c.name}
          />
        ))}
        {props.length > 6 && <span className="mplayer-prop-more">+{props.length-6}</span>}
      </div>
    </div>
  );
}

// ─── Chat Log ──────────────────────────────────────────────
function ChatLog({ log }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log]);
  return (
    <div className="mchat" ref={ref}>
      {log.map((msg, i) => (
        <div key={i} className="mchat-line">{msg}</div>
      ))}
    </div>
  );
}

// ─── Card Modal ────────────────────────────────────────────
function CardModal({ card, onDismiss }) {
  if (!card) return null;
  return (
    <div className="mmodal-overlay">
      <div className="mmodal">
        <div className="mmodal-icon">
          {card.action?.type === 'collect' || card.action?.type === 'birthday' ? '💰' :
           card.action?.type === 'pay' || card.action?.type === 'repairs' ? '💸' :
           card.action?.type === 'jail' ? '👮' :
           card.action?.type === 'jailFree' ? '🆓' :
           card.action?.type === 'goto' ? '🚀' : '🃏'}
        </div>
        <div className="mmodal-text">{card.text}</div>
        <button className="btn btn-primary" onClick={onDismiss}>OK</button>
      </div>
    </div>
  );
}

// ─── Property Card (build panel) ──────────────────────────
function BuildPanel({ cells, current, onBuild, players }) {
  const player = players[current];
  const buildable = cells.filter(c => {
    if (c.owner !== current || c.type !== 'street' || c.hotel) return false;
    if (!hasMonopoly(cells, current, c.colorGroup)) return false;
    const group = cells.filter(x => x.colorGroup === c.colorGroup);
    const minH   = Math.min(...group.map(x => x.hotel ? 5 : (x.houses || 0)));
    const thisH  = c.hotel ? 5 : (c.houses || 0);
    return thisH === minH && player.money >= c.houseCost;
  });

  if (buildable.length === 0) return null;
  return (
    <div className="mbuild-panel">
      <div className="mbuild-title">🏗️ Строить дом/отель:</div>
      {buildable.map(c => (
        <button key={c.pos} className="btn btn-sm mbuild-btn" onClick={() => onBuild(c.pos)}>
          <span className="mbuild-dot" style={{ background: COLOR_MAP[c.colorGroup] }} />
          {c.name} ({c.houses >= 4 ? 'отель' : `д.${(c.houses||0)+1}`}) −{c.houseCost}₽
        </button>
      ))}
    </div>
  );
}

// ─── Main Game ─────────────────────────────────────────────
const BOARD_PX  = 700;
const ZOOM_MIN  = 0.4;
const ZOOM_MAX  = 2.5;
const ZOOM_STEP = 0.2;
const VIEW_H    = 360; // fixed viewport height for the board window

export default function MonopolyGame({ user }) {
  // ── Multiplayer state ──────────────────────────────────
  const [screen, setScreen] = useState(() => {
    const gid = new URLSearchParams(window.location.search).get('game');
    return gid ? 'guest-accept' : 'start';
  });
  const [gameMode, setGameMode]       = useState('bot');   // 'bot' | 'multi'
  const [sessionId, setSessionId]     = useState(
    () => new URLSearchParams(window.location.search).get('game') || null
  );
  const [myPlayerIndex, setMyPlayerIndex] = useState(0);   // 0=host, 1=guest
  const [opponentName, setOpponentName]   = useState('');
  const [onlineMembers, setOnlineMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [inviteLoading, setInviteLoading]   = useState(false);
  const [hostInfo, setHostInfo]         = useState(null);  // for guest screen

  const pollRef          = useRef(null);
  const isSyncFromServer = useRef(false);
  const lastPushedRef    = useRef(null);

  // ── Game state ────────────────────────────────────────
  const [state, dispatch] = useReducer(reducer, null, () => INITIAL_STATE(user?.first_name || 'Игрок'));
  const botTimerRef = useRef(null);

  const [zoom, setZoom] = useState(0.62);
  const [pan,  setPan]  = useState({ x: 0, y: 0 });

  // refs for drag & pinch
  const gestureRef = useRef({
    dragging: false,
    startX: 0, startY: 0,
    panX: 0,   panY: 0,
    pinchDist: null,
  });

  function zoomIn()  { setZoom(z => +Math.min(z + ZOOM_STEP, ZOOM_MAX).toFixed(2)); }
  function zoomOut() { setZoom(z => +Math.max(z - ZOOM_STEP, ZOOM_MIN).toFixed(2)); }

  /* ── Mouse drag ── */
  function onMouseDown(e) {
    e.preventDefault();
    gestureRef.current = { ...gestureRef.current, dragging: true,
      startX: e.clientX, startY: e.clientY,
      panX: pan.x, panY: pan.y };
  }
  function onMouseMove(e) {
    if (!gestureRef.current.dragging) return;
    setPan({
      x: gestureRef.current.panX + (e.clientX - gestureRef.current.startX),
      y: gestureRef.current.panY + (e.clientY - gestureRef.current.startY),
    });
  }
  function onMouseUp() { gestureRef.current.dragging = false; }

  /* ── Touch: drag (1 finger) + pinch (2 fingers) ── */
  function onTouchStart(e) {
    if (e.touches.length === 1) {
      gestureRef.current = { ...gestureRef.current, dragging: true,
        startX: e.touches[0].clientX, startY: e.touches[0].clientY,
        panX: pan.x, panY: pan.y };
    } else if (e.touches.length === 2) {
      gestureRef.current.dragging = false;
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      gestureRef.current.pinchDist = Math.hypot(dx, dy);
    }
  }
  function onTouchMove(e) {
    e.preventDefault();
    if (e.touches.length === 2) {
      // pinch zoom
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const newDist = Math.hypot(dx, dy);
      const prev = gestureRef.current.pinchDist || newDist;
      const delta = (newDist - prev) / 250;
      setZoom(z => +Math.min(Math.max(z + delta, ZOOM_MIN), ZOOM_MAX).toFixed(2));
      gestureRef.current.pinchDist = newDist;
    } else if (e.touches.length === 1 && gestureRef.current.dragging) {
      // drag pan
      setPan({
        x: gestureRef.current.panX + (e.touches[0].clientX - gestureRef.current.startX),
        y: gestureRef.current.panY + (e.touches[0].clientY - gestureRef.current.startY),
      });
    }
  }
  function onTouchEnd(e) {
    if (e.touches.length === 0) {
      gestureRef.current.dragging  = false;
      gestureRef.current.pinchDist = null;
    }
  }

  // ── Multiplayer: Host waits for guest to join ─────────
  useEffect(() => {
    if (screen !== 'host-waiting') return;
    const poll = async () => {
      try {
        const r = await api.get(`/game/session/${sessionId}`);
        if (r.data.status === 'active') {
          clearInterval(pollRef.current);
          const guestName = r.data.guest_name || 'Гость';
          setOpponentName(guestName);
          const myName = user?.first_name || 'Игрок';
          const newState = {
            ...INITIAL_STATE(myName),
            players: [
              { ...initPlayers(myName)[0] },
              { ...initPlayers(myName)[1], name: guestName },
            ],
          };
          isSyncFromServer.current = false;
          dispatch({ type: 'SYNC_STATE', state: newState });
          await api.post(`/game/action/${sessionId}`, { state: newState });
          lastPushedRef.current = newState;
          setGameMode('multi');
          setMyPlayerIndex(0);
          setScreen('playing');
        }
      } catch {}
    };
    pollRef.current = setInterval(poll, 2000);
    return () => clearInterval(pollRef.current);
  }, [screen, sessionId]); // eslint-disable-line

  // ── Multiplayer: Guest waits for initial state ─────────
  useEffect(() => {
    if (screen !== 'guest-waiting') return;
    const poll = async () => {
      try {
        const r = await api.get(`/game/session/${sessionId}`);
        if (r.data.status === 'active' && r.data.state) {
          clearInterval(pollRef.current);
          setOpponentName(r.data.host_name || 'Хост');
          const serverState = r.data.state;
          const myName = user?.first_name || 'Игрок';
          const updatedState = {
            ...serverState,
            players: [
              serverState.players[0],
              { ...serverState.players[1], name: myName },
            ],
          };
          isSyncFromServer.current = true;
          dispatch({ type: 'SYNC_STATE', state: updatedState });
          await api.post(`/game/action/${sessionId}`, { state: updatedState });
          lastPushedRef.current = updatedState;
          setGameMode('multi');
          setMyPlayerIndex(1);
          setScreen('playing');
        }
      } catch {}
    };
    pollRef.current = setInterval(poll, 2000);
    return () => clearInterval(pollRef.current);
  }, [screen, sessionId]); // eslint-disable-line

  // ── Multiplayer: Push state to server after my actions ─
  useEffect(() => {
    if (screen !== 'playing' || gameMode !== 'multi') return;
    if (isSyncFromServer.current) {
      isSyncFromServer.current = false;
      return;
    }
    if (state === lastPushedRef.current) return;
    lastPushedRef.current = state;
    api.post(`/game/action/${sessionId}`, { state }).catch(() => {});
  }, [state]); // eslint-disable-line

  // ── Multiplayer: Poll for opponent moves ───────────────
  useEffect(() => {
    if (screen !== 'playing' || gameMode !== 'multi') return;
    const { current: cur } = state;
    if (cur === myPlayerIndex) {
      clearInterval(pollRef.current);
      return;
    }
    const poll = async () => {
      try {
        const r = await api.get(`/game/session/${sessionId}`);
        if (!r.data.state) return;
        const srv = r.data.state;
        if (JSON.stringify(srv) !== JSON.stringify(state)) {
          isSyncFromServer.current = true;
          dispatch({ type: 'SYNC_STATE', state: srv });
        }
      } catch {}
    };
    pollRef.current = setInterval(poll, 2000);
    return () => clearInterval(pollRef.current);
  }, [screen, gameMode, state.current, myPlayerIndex, sessionId]); // eslint-disable-line

  // ── Multiplayer: actions ───────────────────────────────
  async function handleInviteScreen() {
    setOnlineMembers([]);
    setMembersLoading(true);
    setScreen('invite');
    try {
      const r = await api.get('/members');
      setOnlineMembers((r.data || []).filter(m => m.is_online && !m.is_me));
    } catch {}
    setMembersLoading(false);
  }

  async function sendInvite(pid, name) {
    setInviteLoading(true);
    try {
      const r = await api.post(`/game/invite/${pid}`);
      setSessionId(r.data.session_id);
      setOpponentName(name);
      setScreen('host-waiting');
    } catch {}
    setInviteLoading(false);
  }

  async function acceptInvite() {
    try {
      const r = await api.post(`/game/join/${sessionId}`);
      setHostInfo({ name: r.data.host_name });
      setOpponentName(r.data.host_name || 'Хост');
      setScreen('guest-waiting');
    } catch (e) {
      alert('Игра уже началась или недоступна');
      setScreen('start');
    }
  }

  function resetToStart() {
    clearInterval(pollRef.current);
    setScreen('start');
    setGameMode('bot');
    setSessionId(null);
    setMyPlayerIndex(0);
    setOpponentName('');
    dispatch({ type: 'RESET', userName: user?.first_name });
  }

  const { cells, players, current, phase, dice, diceAnim, log, card, winner } = state;

  // Tokens per cell
  const tokensByCell = {};
  players.forEach(p => {
    if (!tokensByCell[p.position]) tokensByCell[p.position] = [];
    tokensByCell[p.position].push({ id: p.id, color: PLAYER_COLORS[p.id], icon: PLAYER_ICONS[p.id] });
  });

  // ── Bot automation ──
  const runBotTurn = useCallback((st) => {
    if (botTimerRef.current) clearTimeout(botTimerRef.current);

    // Step 1: Roll dice
    botTimerRef.current = setTimeout(() => {
      const d = rollDice();
      dispatch({ type:'DICE_ANIM', v:true });

      botTimerRef.current = setTimeout(() => {
        dispatch({ type:'DICE_ANIM', v:false });
        dispatch({ type:'ROLL', dice: d });

        // Step 2: After landing, decide action
        botTimerRef.current = setTimeout(() => {
          const decision = getAiDecision(st, 1);
          decision.thoughts.forEach(t => dispatch({ type:'_LOG', msg: `🤖 ${t}` }));

          if (decision.action === 'buy') {
            dispatch({ type:'BUY' });
          } else if (decision.action === 'build') {
            dispatch({ type:'BUILD', pos: decision.targetPos });
            botTimerRef.current = setTimeout(() => dispatch({ type:'END_TURN' }), 800);
            return;
          }

          botTimerRef.current = setTimeout(() => dispatch({ type:'END_TURN' }), 800);
        }, 1000);
      }, 700);
    }, 800);
  }, []);

  // Watch for bot's turn (bot mode only)
  useEffect(() => {
    if (gameMode !== 'bot') return;
    if (current === 1 && phase === 'roll' && !players[1].bankrupt) {
      runBotTurn(state);
    }
    if (current === 1 && phase === 'action') {
      // After landing (paid rent, special cell, bought, etc.) — end turn
      botTimerRef.current = setTimeout(() => dispatch({ type:'END_TURN' }), 900);
    }
    if (current === 1 && phase === 'card') {
      botTimerRef.current = setTimeout(() => dispatch({ type:'DISMISS_CARD' }), 1500);
    }
    if (current === 1 && phase === 'buy') {
      // Bot auto-decides
      botTimerRef.current = setTimeout(() => {
        const cell = cells[players[1].position];
        const bot  = players[1];
        if (cell && bot.money >= cell.price && (bot.money - cell.price) > 200) {
          dispatch({ type:'BUY' });
        } else {
          dispatch({ type:'SKIP_BUY' });
        }
      }, 800);
    }
    return () => { if (botTimerRef.current) clearTimeout(botTimerRef.current); };
  }, [current, phase, gameMode]); // eslint-disable-line

  // Handle LOG_THOUGHT (need extra reducer action)
  const dispatchWithThought = useCallback((action) => {
    if (action.type === 'LOG_THOUGHT') {
      dispatch({ type:'_LOG', msg: action.msg });
    } else {
      dispatch(action);
    }
  }, []);

  function handleRoll() {
    if (!isMyTurn || phase !== 'roll') return;
    const d = rollDice();
    dispatch({ type:'DICE_ANIM', v:true });
    setTimeout(() => {
      dispatch({ type:'DICE_ANIM', v:false });
      dispatch({ type:'ROLL', dice: d });
    }, 600);
  }

  const isMyTurn    = gameMode === 'bot' ? current === 0 : current === myPlayerIndex;
  const currentPlayer = players[current];
  const canRoll     = isMyTurn && phase === 'roll';
  const canBuy      = isMyTurn && phase === 'buy';
  const canEndTurn  = isMyTurn && phase === 'action';
  const opponentIdx = myPlayerIndex === 0 ? 1 : 0;

  // ── Screen: mode select ────────────────────────────────
  if (screen === 'start') {
    return (
      <div className="mono-start-screen">
        <div className="mono-start-logo">🎲</div>
        <div className="mono-start-title">Монополия</div>
        <div className="mono-start-subtitle">FIRE35 Edition</div>
        <div className="mono-start-btns">
          <button className="btn btn-primary" onClick={() => {
            setGameMode('bot');
            dispatch({ type:'RESET', userName: user?.first_name });
            setMyPlayerIndex(0);
            setScreen('playing');
          }}>
            🤖 Играть с ботом
          </button>
          <button className="btn" onClick={handleInviteScreen}>
            👥 Пригласить участника
          </button>
        </div>
      </div>
    );
  }

  // ── Screen: invite members ─────────────────────────────
  if (screen === 'invite') {
    return (
      <div className="mono-invite-screen">
        <button className="mono-back-btn" onClick={() => setScreen('start')}>← Назад</button>
        <div className="mono-invite-title">Кого пригласить?</div>
        <div className="mono-invite-hint">Участники онлайн сейчас:</div>
        {membersLoading && <div style={{textAlign:'center',padding:20}}><div className="spinner" /></div>}
        {!membersLoading && onlineMembers.length === 0 && (
          <div className="mono-invite-empty">😴 Нет участников онлайн</div>
        )}
        {onlineMembers.map(m => (
          <button
            key={m.pid}
            className="mono-invite-row"
            onClick={() => sendInvite(m.pid, m.first_name || m.pid)}
            disabled={inviteLoading}
          >
            <span className="online-dot-inline" />
            <div className="mono-invite-info">
              <span className="mono-invite-name">{m.first_name} {m.last_name}</span>
              {m.profession && <span className="mono-invite-prof">{m.profession}</span>}
            </div>
            <span className="mono-invite-arrow">🎲</span>
          </button>
        ))}
      </div>
    );
  }

  // ── Screen: host waiting ───────────────────────────────
  if (screen === 'host-waiting') {
    return (
      <div className="mono-waiting-screen">
        <div className="spinner" />
        <div className="mono-waiting-text">Ждём {opponentName}...</div>
        <div className="mono-waiting-hint">Приглашение отправлено в Telegram 📲</div>
        <button className="btn" style={{marginTop:16}} onClick={resetToStart}>Отмена</button>
      </div>
    );
  }

  // ── Screen: guest accept ───────────────────────────────
  if (screen === 'guest-accept') {
    return (
      <div className="mono-waiting-screen">
        <div style={{fontSize:48}}>🎲</div>
        <div className="mono-waiting-text">Вас приглашают в Монополию!</div>
        <div className="mono-waiting-hint">Участник FIRE35 ждёт вас за игровым столом</div>
        <div style={{display:'flex',gap:10,marginTop:16}}>
          <button className="btn btn-primary" onClick={acceptInvite}>✅ Принять</button>
          <button className="btn" onClick={resetToStart}>Отклонить</button>
        </div>
      </div>
    );
  }

  // ── Screen: guest waiting for host to init ─────────────
  if (screen === 'guest-waiting') {
    return (
      <div className="mono-waiting-screen">
        <div className="spinner" />
        <div className="mono-waiting-text">Ждём начала игры от {opponentName}...</div>
      </div>
    );
  }

  return (
    <div className="mono-wrap">
      {/* Back to start button */}
      <div className="mono-topbar">
        <button className="mono-back-btn" onClick={resetToStart}>← Меню</button>
        {gameMode === 'multi' && (
          <span className="mono-multi-badge">
            {isMyTurn ? '🟢 Ваш ход' : `⏳ Ход ${players[opponentIdx]?.name}`}
          </span>
        )}
      </div>

      {/* Player cards */}
      <div className="mono-players">
        <PlayerCard player={players[0]} isActive={current===0} cells={cells} />
        <PlayerCard player={players[1]} isActive={current===1} cells={cells} />
      </div>

      {/* Zoom + hint */}
      <div className="mono-zoom-bar">
        <button className="mono-zoom-btn" onClick={zoomOut} disabled={zoom <= ZOOM_MIN}>−</button>
        <span className="mono-zoom-val">{Math.round(zoom * 100)}%</span>
        <button className="mono-zoom-btn" onClick={zoomIn}  disabled={zoom >= ZOOM_MAX}>+</button>
        <span className="mono-zoom-hint">🤌 пинч · ✋ тяни доску</span>
      </div>

      {/* Board viewport — fixed height, overflow hidden, drag inside */}
      <div
        className="mono-board-outer"
        style={{ height: VIEW_H, cursor: gestureRef.current.dragging ? 'grabbing' : 'grab' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div
          className="mono-board"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'top left',
            width:  BOARD_PX,
            height: BOARD_PX,
          }}
        >
          {/* Center */}
          <div className="mono-center">
            <div className="mono-logo">🎲 МОНОПОЛИЯ</div>
            <div className="mono-subtitle">Москва</div>
            <Dice dice={dice} rolling={diceAnim} />
            {phase === 'gameover' && (
              <div className="mono-winner">
                🏆 {players[winner]?.name} победил!
                <button className="btn btn-primary btn-sm" style={{marginTop:8}}
                  onClick={gameMode === 'multi' ? resetToStart : () => dispatch({ type:'RESET', userName: user?.first_name })}>
                  {gameMode === 'multi' ? 'В меню' : 'Играть снова'}
                </button>
              </div>
            )}
          </div>

          {/* Cells */}
          {cells.map((cell, i) => (
            <BoardCell
              key={cell.pos}
              cell={cell}
              side={CELL_SIDE[i]}
              tokens={tokensByCell[cell.pos] || []}
              isCorner={[0,10,20,30].includes(cell.pos)}
            />
          ))}
        </div>
      </div>

      {/* Action Panel */}
      <div className="mono-actions">
        {canRoll && (
          <button className="btn btn-primary mono-btn-roll" onClick={handleRoll}>
            🎲 Бросить кубики
          </button>
        )}
        {!isMyTurn && phase === 'roll' && gameMode === 'bot' && (
          <div className="mono-bot-thinking">🤖 Бот думает...</div>
        )}
        {!isMyTurn && phase === 'roll' && gameMode === 'multi' && (
          <div className="mono-bot-thinking">⏳ Ход {players[opponentIdx]?.name}...</div>
        )}
        {canBuy && (() => {
          const cell = cells[players[myPlayerIndex].position];
          return (
            <div className="mono-buy-panel">
              <div className="mono-buy-info">
                <span className="mono-buy-icon" style={{ background: cell?.colorGroup ? COLOR_MAP[cell.colorGroup] : '#888' }} />
                <b>{cell?.name}</b> — {cell?.price}₽
              </div>
              <div className="mono-buy-btns">
                <button className="btn btn-primary" onClick={() => dispatch({ type:'BUY' })}>
                  ✅ Купить
                </button>
                <button className="btn" onClick={() => dispatch({ type:'SKIP_BUY' })}>
                  ❌ Пропустить
                </button>
              </div>
            </div>
          );
        })()}
        {canEndTurn && (
          <>
            {currentPlayer.inJail && (
              <button className="btn" onClick={() => dispatch({ type:'PAY_JAIL' })}
                disabled={currentPlayer.money < 50}>
                🔓 Выкупиться (50₽)
              </button>
            )}
            <BuildPanel cells={cells} current={myPlayerIndex} players={players}
              onBuild={pos => dispatch({ type:'BUILD', pos })} />
            <button className="btn btn-sm mono-btn-end" onClick={() => dispatch({ type:'END_TURN' })}>
              ⏭ Завершить ход
            </button>
          </>
        )}
      </div>

      {/* Chat Log */}
      <ChatLog log={log} />

      {/* Card Modal */}
      {phase === 'card' && isMyTurn && (
        <CardModal card={card} onDismiss={() => dispatch({ type:'DISMISS_CARD' })} />
      )}
    </div>
  );
}
