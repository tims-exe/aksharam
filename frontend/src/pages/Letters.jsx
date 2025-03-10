import { useState, useEffect } from "react";
import api from "../api";
import Navbar from "../components/Navbar";
import Divider from "../components/Divider";
import { useNavigate } from 'react-router-dom';

const Letters = () => {
  const [letters, setLetters] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    getLetters();
  }, []);

  const getLetters = () => {
    api
      .get("/api/letters/")
      .then((res) => res.data)
      .then((data) => {
        setLetters(data);
        console.log(data);
      })
      .catch((err) => alert(err));
  };

  const handleClick = (letter) => {
    navigate(`/letters/${letter.id}`, { state: { letter } });
  };

  return (
    <div className="bg-a_bg pb-20">
      <Navbar activeIndex={1} />
      <div className="flex flex-row justify-between items-center px-[100px] text-a_sc text-[60px]">
        <div className="flex flex-col gap-5 pl-[40px]">
          <p className="font-inria">Malayalam<br />Letters</p>
          <p className="font-arima">മലയാളം<br />അക്ഷരങ്ങൾ</p>
          <p className="text-black font-inria text-[20px]">Master Malayalam script with <br /> interactive writing, AI-powered <br /> feedback, and real-world examples!</p>
        </div>
        <button className="w-32 font-inria self-end mb-20 text-[20px] text-a_bg py-3 bg-a_sc rounded-3xl ml-[90px]">
          <p>Start</p>
        </button>
        <img src="/assets/letter.png" alt="letter" className="w-[600px]" />
      </div>
      <div className="px-5">
        <Divider />
      </div>
      <div className="flex flex-col items-center font-inria">
        <p className="text-text_green my-[50px] text-[35px]">Letters</p>
        <div className="flex flex-wrap gap-16 justify-center px-5">
          {letters.map((item) => (
            <button
              key={item.id}
              className="bg-transparent text-black px-4 py-2 rounded-xl font-arima text-[50px] border-[3px] border-black"
              onClick={() => handleClick(item)} 
            >
              {item.letter}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Letters;
